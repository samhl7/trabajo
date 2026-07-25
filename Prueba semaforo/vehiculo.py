import pygame
import random

# Carril hermano por y fija (derecha/izquierda no dependen de qué calle es)
CARRILES_HERMANOS = {
    "derecha":   {362: 412, 412: 362},
    "izquierda": {262: 312, 312: 262},
}

def _carril_hermano(direccion, lateral, calles_x=()):
    """Carril gemelo para poder cambiarse. Derecha/izquierda usan la tabla fija;
    arriba/abajo dependen de a cuál calle pertenece el carril (calle_x + 14 = sube,
    calle_x + 84 = baja), así que se calculan según las calles reales del mapa."""
    if direccion in ("derecha", "izquierda"):
        return CARRILES_HERMANOS.get(direccion, {}).get(lateral)
    for cx in calles_x:
        if abs(lateral - (cx + 14)) < 3:
            return cx + 84
        if abs(lateral - (cx + 84)) < 3:
            return cx + 14
    return None

class Vehiculo:
    def __init__(self, x, y, ancho, alto, color, velocidad, direccion, semaforos, tipo="auto"):
        self.x = x
        self.y = y
        self.ancho = ancho
        self.alto = alto
        self.color = color
        self.velocidad_maxima = velocidad
        self.velocidad = velocidad
        self.direccion = direccion
        self.semaforos = semaforos
        self.tipo = tipo
        self.es_emergencia = tipo in ("ambulancia", "bomberos")  # ignora el rojo, los demás le ceden el paso
        self.tick_luces = 0

        self.ha_girado = False
        self.decision_giro = random.choice(["recto", "giro", "recto"])
        self.tiempo_esperando = 0  # ms detenido, para estadísticas

        self.angulo_offset = 0.0  # animación del giro visual

        self.carril_objetivo = None  # destino durante un cambio de carril
        self.frames_drift_bloqueado = 0

    def mover(self, ancho_pantalla, alto_pantalla, c1_x, c2_x, semaforos_totales, todos_los_vehiculos=()):
        # Solo el carril interior puede doblar
        if not self.ha_girado and (self.decision_giro == "giro" or self.es_emergencia):
            # Intersección 1 (Sube): el carril izquierdo es el único que sube, nunca al azar
            if self.direccion == "derecha" and self.y == 362 and abs((self.x + self.ancho//2) - (c1_x + 70)) < 6:
                carril_destino = c1_x + 14
                # No gira si el destino está ocupado o lleno
                tope = 250 - (self.ancho + 45)
                rect_destino = pygame.Rect(carril_destino, tope, self.alto, self.y + self.ancho - tope).inflate(24, 24)
                if not any(v is not self and rect_destino.colliderect(v.obtener_rectangulo()) for v in todos_los_vehiculos):
                    self.x = carril_destino
                    self.direccion = "arriba"
                    self.ancho, self.alto = self.alto, self.ancho
                    self.ha_girado = True
                    self.angulo_offset = -90.0
                    self.semaforos = [s for s in semaforos_totales if s.id == "SEM-C1-CALLE"]

            # Intersección 2 (Baja): el carril derecho es el único que baja, nunca al azar
            elif self.direccion == "izquierda" and self.y == 312 and abs((self.x + self.ancho//2) - (c2_x + 70)) < 6:
                carril_destino = c2_x + 84
                # Igual que el cruce 1 pero hacia el sur
                fondo = 450 + self.ancho + 45
                rect_destino = pygame.Rect(carril_destino, self.y, self.alto, fondo - self.y).inflate(24, 24)
                if not any(v is not self and rect_destino.colliderect(v.obtener_rectangulo()) for v in todos_los_vehiculos):
                    self.x = carril_destino
                    self.direccion = "abajo"
                    self.ancho, self.alto = self.alto, self.ancho
                    self.ha_girado = True
                    self.angulo_offset = -90.0
                    self.semaforos = [s for s in semaforos_totales if s.id == "SEM-C2-CALLE"]

        if self.direccion == "derecha":     self.x += self.velocidad
        elif self.direccion == "izquierda": self.x -= self.velocidad
        elif self.direccion == "abajo":     self.y += self.velocidad
        elif self.direccion == "arriba":    self.y -= self.velocidad

        # Deriva lateral hacia el carril hermano
        if self.carril_objetivo is not None:
            paso = 1.2
            if self.direccion in ("derecha", "izquierda"):
                delta = self.carril_objetivo - self.y
                self.y = self.carril_objetivo if abs(delta) <= paso else self.y + (paso if delta > 0 else -paso)
                if self.y == self.carril_objetivo: self.carril_objetivo = None
            else:
                delta = self.carril_objetivo - self.x
                self.x = self.carril_objetivo if abs(delta) <= paso else self.x + (paso if delta > 0 else -paso)
                if self.x == self.carril_objetivo: self.carril_objetivo = None

        if self.angulo_offset < 0:
            self.angulo_offset = min(0.0, self.angulo_offset + 9)

    def _dibujar_cuerpo(self, superficie, ox, oy):
        pygame.draw.rect(superficie, self.color, (ox, oy, self.ancho, self.alto), border_radius=4)
        pygame.draw.rect(superficie, (30, 30, 30), (ox, oy, self.ancho, self.alto), 1, border_radius=4)

        c_vidrio = (130, 200, 230)
        c_faro_del = (255, 250, 200)
        c_faro_tras = (230, 40, 40)

        if self.direccion == "derecha":
            pygame.draw.rect(superficie, c_vidrio, (ox + self.ancho - 11, oy + 2, 3, self.alto - 4))
            pygame.draw.rect(superficie, c_faro_del, (ox + self.ancho - 2, oy + 2, 2, 3))
            pygame.draw.rect(superficie, c_faro_del, (ox + self.ancho - 2, oy + self.alto - 5, 2, 3))
            pygame.draw.rect(superficie, c_faro_tras, (ox, oy + 1, 2, 3))
            pygame.draw.rect(superficie, c_faro_tras, (ox, oy + self.alto - 4, 2, 3))
        elif self.direccion == "izquierda":
            pygame.draw.rect(superficie, c_vidrio, (ox + 8, oy + 2, 3, self.alto - 4))
            pygame.draw.rect(superficie, c_faro_del, (ox, oy + 2, 2, 3))
            pygame.draw.rect(superficie, c_faro_del, (ox, oy + self.alto - 5, 2, 3))
            pygame.draw.rect(superficie, c_faro_tras, (ox + self.ancho - 2, oy + 1, 2, 3))
            pygame.draw.rect(superficie, c_faro_tras, (ox + self.ancho - 2, oy + self.alto - 4, 2, 3))
        elif self.direccion == "abajo":
            pygame.draw.rect(superficie, c_vidrio, (ox + 2, oy + self.alto - 11, self.ancho - 4, 3))
            pygame.draw.rect(superficie, c_faro_del, (ox + 2, oy + self.alto - 2, 3, 2))
            pygame.draw.rect(superficie, c_faro_del, (ox + self.ancho - 5, oy + self.alto - 2, 3, 2))
            pygame.draw.rect(superficie, c_faro_tras, (ox + 1, oy, 3, 2))
            pygame.draw.rect(superficie, c_faro_tras, (ox + self.ancho - 4, oy, 3, 2))
        elif self.direccion == "arriba":
            pygame.draw.rect(superficie, c_vidrio, (ox + 2, oy + 8, self.ancho - 4, 3))
            pygame.draw.rect(superficie, c_faro_del, (ox + 2, oy, 3, 2))
            pygame.draw.rect(superficie, c_faro_del, (ox + self.ancho - 5, oy, 3, 2))
            pygame.draw.rect(superficie, c_faro_tras, (ox + 1, oy + self.alto - 2, 3, 2))
            pygame.draw.rect(superficie, c_faro_tras, (ox + self.ancho - 4, oy + self.alto - 2, 3, 2))

    def dibujar(self, pantalla):
        if self.angulo_offset == 0:
            self._dibujar_cuerpo(pantalla, self.x, self.y)
        else:
            # Dibuja rotado mientras dura la animación del giro
            lienzo = pygame.Surface((self.ancho, self.alto), pygame.SRCALPHA)
            self._dibujar_cuerpo(lienzo, 0, 0)
            girado = pygame.transform.rotate(lienzo, self.angulo_offset)
            rect = girado.get_rect(center=(self.x + self.ancho / 2, self.y + self.alto / 2))
            pantalla.blit(girado, rect)

        if self.es_emergencia:
            self.tick_luces += 1
            pygame.draw.rect(pantalla, (240, 20, 20), (self.x + self.ancho//2 - 2, self.y + self.alto//2 - 4, 4, 8) if self.direccion in ["abajo","arriba"] else (self.x + self.ancho//2 - 4, self.y + self.alto//2 - 2, 8, 4))
            color_alterno = (0, 120, 255) if self.tipo == "ambulancia" else (255, 255, 255)
            color_luz = (255, 0, 0) if (self.tick_luces // 5) % 2 == 0 else color_alterno
            pygame.draw.circle(pantalla, color_luz, (self.x + self.ancho//2, self.y + self.alto//2), 4)

    def obtener_rectangulo(self):
        return pygame.Rect(self.x, self.y, self.ancho, self.alto)

    def snapshot(self):
        """Guarda todo lo que 'mover()' puede cambiar en un frame (incluido un giro,
        que cambia dirección y hasta ancho/alto). Sirve para poder revertir el
        vehículo a su último estado seguro si terminó encimado con otro."""
        return (self.x, self.y, self.direccion, self.ancho, self.alto,
                self.ha_girado, self.angulo_offset, self.carril_objetivo)

    def restaurar(self, estado):
        (self.x, self.y, self.direccion, self.ancho, self.alto,
         self.ha_girado, self.angulo_offset, self.carril_objetivo) = estado
        self.velocidad = 0

    def _prioridad(self):
        # Desempate en cruces perpendiculares: emergencia siempre gana
        return (self.es_emergencia, {"derecha": 3, "izquierda": 2, "abajo": 1, "arriba": 0}[self.direccion])

    def _intentar_cambio_carril(self, todos_los_vehiculos, calles_x=(280, 720)):
        # Adelantar por el carril hermano en vez de frenar detrás del de adelante
        if self.carril_objetivo is not None:
            return False
        if self.decision_giro == "giro" and not self.ha_girado:
            return False
        # Prohibido cambiar de carril dentro de una intersección
        if self.direccion in ("derecha", "izquierda"):
            if any(b - 90 < self.x + self.ancho and self.x < b + 140 + 90 for b in calles_x):
                return False
        elif self.y + self.alto > 250 - 90 and self.y < 450 + 90:
            return False
        lateral = self.y if self.direccion in ("derecha", "izquierda") else self.x
        destino = _carril_hermano(self.direccion, lateral, calles_x)
        if destino is None:
            return False
        # El carril destino debe estar libre en una ventana amplia (adelante y atrás)
        if self.direccion in ("derecha", "izquierda"):
            zona = pygame.Rect(self.x - 130, destino - 6, self.ancho + 260, self.alto + 12)
            avance_propio = self.x
        else:
            zona = pygame.Rect(destino - 6, self.y - 130, self.ancho + 12, self.alto + 260)
            avance_propio = self.y
        for v in todos_los_vehiculos:
            if v is self:
                continue
            if zona.colliderect(v.obtener_rectangulo()):
                return False
            if v.direccion == self.direccion and v.carril_objetivo == destino:
                avance_otro = v.x if self.direccion in ("derecha", "izquierda") else v.y
                if abs(avance_otro - avance_propio) < 130:
                    return False
        self.carril_objetivo = destino
        return True

    def _cruce_bloqueado(self, linea, ancho_cruce, todos_los_vehiculos):
        # ¿algún vehículo de mi carril me dejaría atravesado a mitad del cruce?
        largo = self.ancho if self.direccion in ("derecha", "izquierda") else self.alto
        tramo = ancho_cruce + largo + 50
        for otro in todos_los_vehiculos:
            if otro is self or otro.direccion != self.direccion:
                continue
            # Un carro a mitad de cambio de carril cuenta en ambos
            if self.direccion in ("derecha", "izquierda"):
                laterales = (otro.y, otro.carril_objetivo)
                cerca = otro.x if self.direccion == "derecha" else otro.x + otro.ancho
                dentro = linea < cerca < linea + tramo if self.direccion == "derecha" else linea - tramo < cerca < linea
                mismo_carril = any(l is not None and abs(self.y - l) < 15 for l in laterales)
            else:
                laterales = (otro.x, otro.carril_objetivo)
                cerca = otro.y if self.direccion == "abajo" else otro.y + otro.alto
                dentro = linea < cerca < linea + tramo if self.direccion == "abajo" else linea - tramo < cerca < linea
                mismo_carril = any(l is not None and abs(self.x - l) < 15 for l in laterales)
            if dentro and mismo_carril:
                return True
        return False

    def puede_avanzar(self, todos_los_vehiculos, peatones=(), calles_x=(280, 720)):
        ok = self._puede_avanzar(todos_los_vehiculos, peatones, calles_x)
        # Si la deriva queda trabada, aborta tras ~45 frames y vuelve al carril de origen
        if self.carril_objetivo is not None:
            if ok:
                self.frames_drift_bloqueado = 0
            else:
                self.frames_drift_bloqueado += 1
                if self.frames_drift_bloqueado > 45:
                    self.carril_objetivo = _carril_hermano(self.direccion, self.carril_objetivo, calles_x)
                    self.frames_drift_bloqueado = 0
        return ok

    def _puede_avanzar(self, todos_los_vehiculos, peatones=(), calles_x=(280, 720)):
        self.velocidad = self.velocidad_maxima

        # --- REGLA: PEATONES --- nadie atropella, ni las emergencias
        if self.direccion == "derecha":
            franja = pygame.Rect(self.x + self.ancho, self.y - 8, 30, self.alto + 16)
        elif self.direccion == "izquierda":
            franja = pygame.Rect(self.x - 30, self.y - 8, 30, self.alto + 16)
        elif self.direccion == "abajo":
            franja = pygame.Rect(self.x - 8, self.y + self.alto, self.ancho + 16, 30)
        else:
            franja = pygame.Rect(self.x - 8, self.y - 30, self.ancho + 16, 30)
        if any(franja.collidepoint(p.x, p.y) for p in peatones):
            self.velocidad = 0; return False

        # --- REGLA: CEDER AL TRÁFICO PERPENDICULAR --- evita que dos cruzados queden trabados a mitad del cruce
        mi_eje_h = self.direccion in ("derecha", "izquierda")
        if self.direccion == "derecha":
            zona_cruzado = pygame.Rect(self.x + self.ancho, self.y, 40, self.alto)
        elif self.direccion == "izquierda":
            zona_cruzado = pygame.Rect(self.x - 40, self.y, 40, self.alto)
        elif self.direccion == "abajo":
            zona_cruzado = pygame.Rect(self.x, self.y + self.alto, self.ancho, 40)
        else:
            zona_cruzado = pygame.Rect(self.x, self.y - 40, self.ancho, 40)
        zona_cruzado = zona_cruzado.inflate(16, 16)
        mi_prio = self._prioridad()
        for otro in todos_los_vehiculos:
            if otro is self or (otro.direccion in ("derecha", "izquierda")) == mi_eje_h:
                continue
            if otro.velocidad > 0 and otro._prioridad() > mi_prio and zona_cruzado.colliderect(otro.obtener_rectangulo()):
                self.velocidad = 0; return False

        # --- REGLA: SEMÁFOROS --- emergencias ignoran el rojo, pero no el cruce lleno
        for sem in self.semaforos:
            if self.direccion == "derecha" and sem.orientacion == "derecha":
                distancia = (sem.x - 15) - (self.x + self.ancho)
                if 0 < distancia < 85:
                    if not self.es_emergencia:
                        if sem.es_rojo(): self.velocidad = 0; return False
                        if sem.es_amarillo(): self.velocidad = max(1, int(self.velocidad_maxima * (distancia / 85)))
                        # Necesita la flecha de giro en verde
                        elif self.decision_giro == "giro" and self.y == 362 and sem.tiene_flecha_giro and not sem.flecha_verde:
                            self.velocidad = 0; return False
                    if self._cruce_bloqueado(sem.x - 15, 180, todos_los_vehiculos):
                        self.velocidad = 0; return False

            elif self.direccion == "izquierda" and sem.orientacion == "izquierda":
                distancia = self.x - (sem.x + 35)
                if 0 < distancia < 85:
                    if not self.es_emergencia:
                        if sem.es_rojo(): self.velocidad = 0; return False
                        if sem.es_amarillo(): self.velocidad = max(1, int(self.velocidad_maxima * (distancia / 85)))
                        elif self.decision_giro == "giro" and self.y == 312 and sem.tiene_flecha_giro and not sem.flecha_verde:
                            self.velocidad = 0; return False
                    if self._cruce_bloqueado(sem.x + 35, 180, todos_los_vehiculos):
                        self.velocidad = 0; return False

            elif self.direccion == "abajo" and sem.orientacion == "abajo":
                distancia = 250 - (self.y + self.alto)
                if 0 < distancia < 85:
                    if not self.es_emergencia:
                        if sem.es_rojo(): self.velocidad = 0; return False
                        if sem.es_amarillo(): self.velocidad = max(1, int(self.velocidad_maxima * (distancia / 85)))
                    if self._cruce_bloqueado(250, 200, todos_los_vehiculos):
                        self.velocidad = 0; return False

            elif self.direccion == "arriba" and sem.orientacion == "arriba":
                distancia = self.y - 450
                if 0 < distancia < 85:
                    if not self.es_emergencia:
                        if sem.es_rojo(): self.velocidad = 0; return False
                        if sem.es_amarillo(): self.velocidad = max(1, int(self.velocidad_maxima * (distancia / 85)))
                    if self._cruce_bloqueado(450, 200, todos_los_vehiculos):
                        self.velocidad = 0; return False

        # --- REGLA: DISTANCIAMIENTO / ANTI-CHOQUES ---
        if self.direccion in ("derecha", "izquierda"):
            lat_propio = self.carril_objetivo if self.carril_objetivo is not None else self.y
        else:
            lat_propio = self.carril_objetivo if self.carril_objetivo is not None else self.x
        bloqueado_por_delante = False
        for otro in todos_los_vehiculos:
            if otro == self: continue
            if self.direccion == otro.direccion:
                # Deja más espacio si el de atrás es una emergencia
                if not self.es_emergencia and otro.es_emergencia:
                    limite_alerta = 120
                else:
                    limite_alerta = 45

                if self.direccion == "derecha" and 0 < (otro.x - (self.x + self.ancho)) < limite_alerta and abs(lat_propio - otro.y) < 15:
                    bloqueado_por_delante = True; break
                elif self.direccion == "izquierda" and 0 < (self.x - (otro.x + otro.ancho)) < limite_alerta and abs(lat_propio - otro.y) < 15:
                    bloqueado_por_delante = True; break
                elif self.direccion == "abajo" and 0 < (otro.y - (self.y + self.alto)) < limite_alerta and abs(lat_propio - otro.x) < 15:
                    bloqueado_por_delante = True; break
                elif self.direccion == "arriba" and 0 < (self.y - (otro.y + otro.alto)) < limite_alerta and abs(lat_propio - otro.x) < 15:
                    bloqueado_por_delante = True; break

        # Nunca rebasa ni se cambia de carril: si hay alguien adelante, se detiene
        # y espera en su propio carril (evita terminar en un carril de sentido
        # contrario, que era la causa real de los choques "de frente").
        if bloqueado_por_delante:
            self.velocidad = 0; return False

        # Red de seguridad genérica anti-choque, sea cual sea la dirección
        nx, ny = self.x, self.y
        if self.direccion == "derecha":     nx += self.velocidad
        elif self.direccion == "izquierda": nx -= self.velocidad
        elif self.direccion == "abajo":     ny += self.velocidad
        elif self.direccion == "arriba":    ny -= self.velocidad
        if self.carril_objetivo is not None:
            paso = 1.2
            if self.direccion in ("derecha", "izquierda"):
                delta = self.carril_objetivo - self.y
                ny = self.carril_objetivo if abs(delta) <= paso else ny + (paso if delta > 0 else -paso)
            else:
                delta = self.carril_objetivo - self.x
                nx = self.carril_objetivo if abs(delta) <= paso else nx + (paso if delta > 0 else -paso)
        futuro = pygame.Rect(nx, ny, self.ancho, self.alto)
        for otro in todos_los_vehiculos:
            if otro is not self and futuro.colliderect(otro.obtener_rectangulo()):
                self.velocidad = 0; return False
        return True