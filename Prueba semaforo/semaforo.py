import pygame

class Semaforo:
    def __init__(self, x, y, direccion, id_semaforo, orientacion="abajo", tiene_flecha_giro=False, carril_giro=None):
        self.x = x
        self.y = y
        self.direccion = direccion
        self.id = id_semaforo
        self.orientacion = orientacion

        if self.direccion == "horizontal":
            self.estado = "verde"
        else:
            self.estado = "rojo"

        # Cuarta luz: flecha de giro a la izquierda protegida
        self.tiene_flecha_giro = tiene_flecha_giro
        self.carril_giro = carril_giro
        self.flecha_verde = False
        self.cola_giro = 0
        self.tiempo_espera_giro = 0
        self._inicio_espera_giro = None

        # Sensor de aglomeración: vehículos en zona y tiempo esperando en rojo
        self.cola = 0
        self.cola_ponderada = 0  # pesada por tipo: ambulancia 4, bomberos 3, auto 1
        self.tiempo_espera = 0
        self._inicio_espera = None
        self.rival_urgente = False
        self.forzado = None  # orden manual del panel: None | "rojo" | "verde"

        self.ultimo_cambio = pygame.time.get_ticks()
        self.duracion_verde = 5000
        self.duracion_amarillo = 2000
        self.duracion_rojo = 5000
        self.tiempo_minimo_verde = 2500
        self.tiempo_maximo_verde = 5000

        # Sensores calibrados ante las líneas de cebra, cubriendo ambos carriles y varios autos de cola
        if self.orientacion == "derecha":
            self.sensor_rect = pygame.Rect(self.x - 240, 355, 220, 90)
        elif self.orientacion == "izquierda":
            self.sensor_rect = pygame.Rect(self.x + 30, 255, 220, 90)
        elif self.orientacion == "abajo":
            self.sensor_rect = pygame.Rect(self.x, 10, 140, 230)
        elif self.orientacion == "arriba":
            self.sensor_rect = pygame.Rect(self.x - 145, 460, 140, 240)

        self.sensor_activo = False
        self.alerta_ambulancia = False
        self.alerta_bomberos = False

    def actualizar(self):
        tiempo_actual = pygame.time.get_ticks()
        transcurrido = tiempo_actual - self.ultimo_cambio

        if self.estado == "verde" and transcurrido >= self.duracion_verde:
            self.estado = "amarillo"
            self.ultimo_cambio = tiempo_actual
        elif self.estado == "amarillo" and transcurrido >= self.duracion_amarillo:
            self.estado = "rojo"
            self.ultimo_cambio = tiempo_actual
        elif self.estado == "rojo" and transcurrido >= self.duracion_rojo:
            self.estado = "verde"
            self.ultimo_cambio = tiempo_actual

    def actualizar_inteligente(self, vehiculos, semaforos_del_cruce, caja_cruce=None, peatones=()):
        tiempo_actual = pygame.time.get_ticks()
        self.alerta_ambulancia = False
        self.alerta_bomberos = False

        en_zona = [v for v in vehiculos if v.obtener_rectangulo().colliderect(self.sensor_rect)]
        self.cola = len(en_zona)
        # Pondera por tipo para dar prioridad a emergencias frente a rivales
        PESOS = {"ambulancia": 4, "bomberos": 3}
        self.cola_ponderada = sum(PESOS.get(getattr(v, "tipo", None), 1) for v in en_zona)
        self.sensor_activo = self.cola > 0
        if any(getattr(v, "tipo", None) == "ambulancia" for v in en_zona):
            self.alerta_ambulancia = True
        if any(getattr(v, "tipo", None) == "bomberos" for v in en_zona):
            self.alerta_bomberos = True

        # Peatones de mi cruce: prioridad máxima
        peatones_del_cruce = [p for p in peatones if p.semaforo is self]
        peaton_esperando = any(not p.cruzando for p in peatones_del_cruce)
        peaton_en_calle = any(p.cruzando and p.en_la_calle() for p in peatones_del_cruce)

        # Cuánto tiempo lleva esperando en rojo con autos detenidos
        if self.sensor_activo and self.estado == "rojo":
            if self._inicio_espera is None:
                self._inicio_espera = tiempo_actual
            self.tiempo_espera = tiempo_actual - self._inicio_espera
        else:
            self._inicio_espera = None
            self.tiempo_espera = 0

        # Cola propia del carril de giro
        if self.tiene_flecha_giro:
            self.cola_giro = sum(1 for v in en_zona if getattr(v, "decision_giro", None) == "giro" and v.y == self.carril_giro)
            if self.cola_giro > 0 and not self.flecha_verde:
                if self._inicio_espera_giro is None:
                    self._inicio_espera_giro = tiempo_actual
                self.tiempo_espera_giro = tiempo_actual - self._inicio_espera_giro
            else:
                self._inicio_espera_giro = None
                self.tiempo_espera_giro = 0

        # Orden manual: STOP congela en rojo, GO fuerza verde de forma segura (ambar a rivales primero)
        if self.forzado == "rojo":
            self.estado = "rojo"
            return
        if self.forzado == "verde":
            if self.estado != "verde":
                for s in semaforos_del_cruce:
                    if s is not self and s.direccion != self.direccion and s.estado == "verde" and s.forzado is None:
                        s.estado = "amarillo"
                        s.ultimo_cambio = tiempo_actual
                rivales_rojos = all(s.direccion == self.direccion or s.es_rojo() for s in semaforos_del_cruce)
                caja_libre = caja_cruce is None or not any(v.obtener_rectangulo().colliderect(caja_cruce) for v in vehiculos)
                if rivales_rojos and caja_libre:
                    self.estado = "verde"
                    self.ultimo_cambio = tiempo_actual
            return

        transcurrido = tiempo_actual - self.ultimo_cambio

        if self.estado == "verde":
            # Un rival congelado con STOP no cuenta como "esperando"
            rivales = [s for s in semaforos_del_cruce if s.direccion != self.direccion]
            rivales_esperando = any(s.sensor_activo and s.estado == "rojo" and s.forzado != "rojo" for s in rivales) or self.rival_urgente
            ambulancia_rival = any(s.alerta_ambulancia for s in rivales)
            bomberos_rival = any(s.alerta_bomberos for s in rivales)
            urgencia_rival = max([s.cola_ponderada + s.tiempo_espera // 1000 for s in rivales if s.estado == "rojo" and s.forzado != "rojo"], default=0)
            # Carril muy aglomerado se queda en verde un poco más
            tiempo_maximo_efectivo = self.tiempo_maximo_verde + min(self.cola_ponderada, 5) * 400

            # Prioridad: peatón > ambulancia > bomberos > autos según aglomeración
            if peaton_esperando:
                self.estado = "amarillo"
                self.ultimo_cambio = tiempo_actual
            elif ambulancia_rival:
                self.estado = "amarillo"
                self.ultimo_cambio = tiempo_actual
            elif bomberos_rival:
                self.estado = "amarillo"
                self.ultimo_cambio = tiempo_actual
            elif transcurrido >= tiempo_maximo_efectivo and rivales_esperando:
                self.estado = "amarillo"
                self.ultimo_cambio = tiempo_actual
            elif transcurrido >= self.tiempo_minimo_verde and rivales_esperando and (not self.sensor_activo or urgencia_rival > self.cola_ponderada):
                self.estado = "amarillo"
                self.ultimo_cambio = tiempo_actual

        elif self.estado == "amarillo" and transcurrido >= self.duracion_amarillo:
            self.estado = "rojo"
            self.ultimo_cambio = tiempo_actual

        elif self.estado == "rojo":
            via_perpendicular_libre = all(s.direccion == self.direccion or s.estado == "rojo" for s in semaforos_del_cruce)
            cruce_despejado = caja_cruce is None or not any(v.obtener_rectangulo().colliderect(caja_cruce) for v in vehiculos)
            # Entre varios rojos, gana el de mayor urgencia (medida en vivo sobre su sensor)
            mi_urgencia = self._urgencia(vehiculos)
            rival_mas_urgente = any(
                s is not self and s.direccion != self.direccion and s.estado == "rojo" and
                s.forzado is None and s._urgencia(vehiculos) > mi_urgencia
                for s in semaforos_del_cruce
            )
            rival_con_go = any(s.direccion != self.direccion and s.forzado == "verde" for s in semaforos_del_cruce)
            # Nunca vuelve a verde mientras un peatón siga cruzando
            if peaton_en_calle or rival_mas_urgente or rival_con_go:
                pass
            elif via_perpendicular_libre and cruce_despejado and (self.alerta_ambulancia or self.sensor_activo):
                self.estado = "verde"
                self.ultimo_cambio = tiempo_actual

    def _urgencia(self, vehiculos):
        # Nivel de prioridad + peso de la cola, en vivo sobre el sensor
        en_zona = [v for v in vehiculos if v.obtener_rectangulo().colliderect(self.sensor_rect)]
        tipos = [getattr(v, "tipo", None) for v in en_zona]
        nivel = 2 if "ambulancia" in tipos else 1 if "bomberos" in tipos else 0
        PESOS = {"ambulancia": 4, "bomberos": 3}
        return (nivel, sum(PESOS.get(t, 1) for t in tipos))

    def dibujar_sensor(self, pantalla):
        # Área de detección en línea punteada: naranja si detecta, gris si no
        color = (255, 170, 60) if self.sensor_activo else (110, 130, 150)
        r = self.sensor_rect
        for x in range(r.left, r.right, 12):
            pygame.draw.line(pantalla, color, (x, r.top), (min(x + 6, r.right), r.top), 1)
            pygame.draw.line(pantalla, color, (x, r.bottom), (min(x + 6, r.right), r.bottom), 1)
        for y in range(r.top, r.bottom, 12):
            pygame.draw.line(pantalla, color, (r.left, y), (r.left, min(y + 6, r.bottom)), 1)
            pygame.draw.line(pantalla, color, (r.right, y), (r.right, min(y + 6, r.bottom)), 1)

    def es_verde(self): return self.estado == "verde"
    def es_amarillo(self): return self.estado == "amarillo"
    def es_rojo(self): return self.estado == "rojo"

    def dibujar(self, pantalla):
        alto_caja = 50 if self.tiene_flecha_giro else 38
        pygame.draw.rect(pantalla, (220, 220, 220), (self.x + 8, self.y + alto_caja - 8, 4, 20))
        pygame.draw.rect(pantalla, (30, 30, 30), (self.x + 3, self.y + alto_caja + 12, 14, 4))
        pygame.draw.rect(pantalla, (20, 20, 20), (self.x, self.y, 20, alto_caja), border_radius=4)

        c_rojo = (255, 20, 20) if self.estado == "rojo" else (50, 0, 0)
        c_amarillo = (255, 210, 0) if self.estado == "amarillo" else (50, 40, 0)
        c_verde = (0, 255, 70) if self.estado == "verde" else (0, 50, 10)

        pygame.draw.circle(pantalla, c_rojo, (self.x + 10, self.y + 7), 4)
        pygame.draw.circle(pantalla, c_amarillo, (self.x + 10, self.y + 19), 4)
        pygame.draw.circle(pantalla, c_verde, (self.x + 10, self.y + 31), 4)

        if self.tiene_flecha_giro:
            c_flecha = (0, 255, 70) if self.flecha_verde else (0, 50, 10)
            cx, cy = self.x + 10, self.y + 43
            pygame.draw.polygon(pantalla, c_flecha, [(cx + 4, cy - 4), (cx + 4, cy + 4), (cx - 4, cy)])
