
import pygame
import sys
import random
import logging
import queue

from vehiculo import Vehiculo
from semaforo import Semaforo
from peaton import Peaton
from sensor_mqtt import iniciar_hilo_mqtt

pygame.init()

# Cola de eventos del sensor físico/simulado (ESP32 vía MQTT); el hilo MQTT
# solo escribe aquí, el loop principal la drena cada frame.
cola_sensores = queue.Queue()
iniciar_hilo_mqtt(cola_sensores)

# Registro de choques reales detectados en juego, para diagnóstico
logging.basicConfig(filename="logChoques.log", level=logging.INFO, format="%(asctime)s %(message)s")
log_choques = logging.getLogger("choques")

# --- CONFIGURACIÓN DE PANTALLA ---
ANCHO_SIM = 1000
ANCHO_PANEL = 330  
ANCHO_TOTAL = ANCHO_SIM + ANCHO_PANEL
ALTO = 860

pantalla = pygame.display.set_mode((ANCHO_TOTAL, ALTO))
pygame.display.set_caption("Panel de Control Vial Integrado")

clock = pygame.time.Clock()

# --- PALETA DE COLORES RE-ESTILIZADA ---
Color_Hierba = (38, 99, 66)        # Un verde parque más vivo y limpio
Color_Asfalto = (54, 57, 60)       
Aceras = (110, 115, 118)           # Gris oscuro sutil para los bordes de los parques
Color_Cebra = (255, 255, 255)
Color_Amarillo_Vial = (244, 208, 111)

# Colores para la vegetación de los parques
Color_Tronco = (100, 70, 50)
Color_Hojas = (28, 82, 52)
Color_Hojas_Luz = (44, 115, 75)

# Panel Lateral Original
PANEL_FONDO = (30, 38, 46)        
PANEL_CARTA = (40, 50, 61)        
BORDE_ESTRUCTURA = (60, 75, 92)   
AZUL_ACENTO = (70, 160, 240)      
TEXTO_PRINCIPAL = (245, 248, 250)
TEXTO_SECUNDARIO = (165, 180, 195)

CALLE_1_X = 120
CALLE_2_X = 430
CALLE_3_X = 740

# --- VARIABLES DE CONTROL ---
reloj_interno = "07:02"
estado_clima = "despejado"
flujo_activo = True

# Tipo de vehículo para el despacho manual (los peatones tienen su propio selector, más abajo)
TIPOS_DISPONIBLES = ["Auto", "Ambulancia", "Bomberos"]
sim_vehiculo_tipo = "Auto"

# Carretera de entrada para el despacho manual de vehículos
DIRECCIONES_DISPONIBLES = ["derecha", "izquierda", "abajo", "arriba"]
ETIQUETAS_DIRECCION = {"derecha": "→ ENT-O", "izquierda": "← ENT-E", "abajo": "↓ ENT-N", "arriba": "↑ ENT-S"}
direccion_seleccionada = "derecha"

cruce_seleccionado = "C1-Oeste"
peatones = []

dropdown_abierto = None  # None | "tipo" | "direccion" | "cruce"

# Semáforos (SEM-C1-O y SEM-C2-E llevan además la 4ta luz: flecha de giro a la izquierda protegida)
sem_c1_oeste = Semaforo(CALLE_1_X - 25, 455, "horizontal", "SEM-C1-O", "derecha", tiene_flecha_giro=True, carril_giro=362)
sem_c1_este  = Semaforo(CALLE_1_X + 145, 210, "horizontal", "SEM-C1-E", "izquierda")
sem_c1_sur   = Semaforo(CALLE_1_X + 145, 455, "vertical", "SEM-C1-CALLE", "arriba")
sem_c1_norte = Semaforo(CALLE_1_X - 25, 210, "vertical", "SEM-C1-NORTE", "abajo")

sem_c2_oeste = Semaforo(CALLE_2_X - 25, 455, "horizontal", "SEM-C2-O", "derecha")
sem_c2_este  = Semaforo(CALLE_2_X + 145, 210, "horizontal", "SEM-C2-E", "izquierda", tiene_flecha_giro=True, carril_giro=312)
sem_c2_norte = Semaforo(CALLE_2_X - 25, 210, "vertical", "SEM-C2-CALLE", "abajo")
sem_c2_sur   = Semaforo(CALLE_2_X + 145, 455, "vertical", "SEM-C2-SUR", "arriba")

# Calle 3 (nueva): mismo esquema de doble sentido que las calles 1 y 2, sin flecha de giro protegida
sem_c3_oeste = Semaforo(CALLE_3_X - 25, 455, "horizontal", "SEM-C3-O", "derecha")
sem_c3_este  = Semaforo(CALLE_3_X + 145, 210, "horizontal", "SEM-C3-E", "izquierda")
sem_c3_norte = Semaforo(CALLE_3_X - 25, 210, "vertical", "SEM-C3-CALLE", "abajo")
sem_c3_sur   = Semaforo(CALLE_3_X + 145, 455, "vertical", "SEM-C3-SUR", "arriba")

# Calle 1, Calle 2 y Calle 3 son de doble sentido: carril izquierdo sube (arriba), carril derecho baja (abajo)
cruce_1 = [sem_c1_oeste, sem_c1_este, sem_c1_sur, sem_c1_norte]
cruce_2 = [sem_c2_oeste, sem_c2_este, sem_c2_norte, sem_c2_sur]
cruce_3 = [sem_c3_oeste, sem_c3_este, sem_c3_norte, sem_c3_sur]
todos_los_semaforos = cruce_1 + cruce_2 + cruce_3

# Cruces peatonales, cada uno ligado al semáforo que controla el tráfico que lo cruza
CRUCES_PEATONALES = {
    "C1-Oeste": {"eje": "y", "fijo": CALLE_1_X - 11, "ini": 248, "fin": 438, "sem": sem_c1_oeste},
    "C1-Sur":   {"eje": "x", "fijo": 460, "ini": CALLE_1_X - 5, "fin": CALLE_1_X + 145, "sem": sem_c1_sur},
    "C1-Norte": {"eje": "x", "fijo": 238, "ini": CALLE_1_X - 5, "fin": CALLE_1_X + 145, "sem": sem_c1_norte},
    "C2-Oeste": {"eje": "y", "fijo": CALLE_2_X - 11, "ini": 248, "fin": 438, "sem": sem_c2_oeste},
    "C2-Norte": {"eje": "x", "fijo": 238, "ini": CALLE_2_X - 5, "fin": CALLE_2_X + 145, "sem": sem_c2_norte},
    "C2-Sur":   {"eje": "x", "fijo": 460, "ini": CALLE_2_X - 5, "fin": CALLE_2_X + 145, "sem": sem_c2_sur},
    "C3-Oeste": {"eje": "y", "fijo": CALLE_3_X - 11, "ini": 248, "fin": 438, "sem": sem_c3_oeste},
    "C3-Norte": {"eje": "x", "fijo": 238, "ini": CALLE_3_X - 5, "fin": CALLE_3_X + 145, "sem": sem_c3_norte},
    "C3-Sur":   {"eje": "x", "fijo": 460, "ini": CALLE_3_X - 5, "fin": CALLE_3_X + 145, "sem": sem_c3_sur},
}
ETIQUETAS_CRUCE = {
    "C1-Oeste": "⇅ C1-Oeste", "C1-Sur": "⇄ C1-Sur", "C1-Norte": "⇄ C1-Norte",
    "C2-Oeste": "⇅ C2-Oeste", "C2-Norte": "⇄ C2-Norte", "C2-Sur": "⇄ C2-Sur",
    "C3-Oeste": "⇅ C3-Oeste", "C3-Norte": "⇄ C3-Norte", "C3-Sur": "⇄ C3-Sur",
}

# Caja física de cada intersección, para no dar verde mientras alguien sigue cruzando
CAJA_CRUCE_1 = pygame.Rect(CALLE_1_X, 250, 140, 200)
CAJA_CRUCE_2 = pygame.Rect(CALLE_2_X, 250, 140, 200)
CAJA_CRUCE_3 = pygame.Rect(CALLE_3_X, 250, 140, 200)
vehiculos = []

ULTERIOR_SPAWN = 0
INTERVALO_SPAWN = 1600

# Estadísticas
PREV_TICK = 0
VEHICULOS_PROCESADOS = 0
TIEMPO_ESPERA_TOTAL_MS = 0

# Fuentes
fnt_mini = pygame.font.SysFont("Verdana", 10, bold=True)
fnt_vial = pygame.font.SysFont("Arial", 12, bold=True)
fnt_standard = pygame.font.SysFont("Verdana", 12)
fnt_resaltada = pygame.font.SysFont("Verdana", 12, bold=True)
fnt_cabecera = pygame.font.SysFont("Verdana", 15, bold=True)

mensajes_consola = [
    "[INFO] Sistema de monitoreo inicializado correctamente.",
    "[VÍA] Modulo de control de intersecciones: ACTIVO.",
    "[MÁQUINA] Flujo vehicular adaptativo iniciado."
]

# Distribución orgánica fija de árboles simulando bosques urbanos en los parques
random.seed(101)
arboles_parques = []
for _ in range(45):
    # Intentar posicionar árboles solo dentro de las zonas que corresponden a los parques (evitando el asfalto)
    ax = random.choice([random.randint(20, CALLE_1_X - 30), random.randint(CALLE_1_X + 160, CALLE_2_X - 30), random.randint(CALLE_2_X + 160, CALLE_3_X - 30), random.randint(CALLE_3_X + 160, ANCHO_SIM - 30)])
    ay = random.choice([random.randint(20, 230), random.randint(470, ALTO - 30)])
    radio = random.randint(8, 13)
    arboles_parques.append((ax, ay, radio))
random.seed()

def dibujar_modulo_propio(superficie, x, y, w, h, titulo):
    pygame.draw.rect(superficie, PANEL_CARTA, (x, y, w, h), border_radius=8)
    pygame.draw.rect(superficie, BORDE_ESTRUCTURA, (x, y, w, h), 1, border_radius=8)
    texto = fnt_mini.render(titulo.upper(), True, AZUL_ACENTO)
    superficie.blit(texto, (x + 14, y + 10))

def dibujar_original_sidebar(superficie):
    bx = ANCHO_SIM + 12
    cw = ANCHO_PANEL - 24

    pygame.draw.rect(superficie, PANEL_FONDO, (ANCHO_SIM, 0, ANCHO_PANEL, ALTO))
    pygame.draw.line(superficie, BORDE_ESTRUCTURA, (ANCHO_SIM, 0), (ANCHO_SIM, ALTO), 2)

    lbl_top = fnt_cabecera.render("CONSOLA DE MONITOREO VIAL", True, TEXTO_PRINCIPAL)
    superficie.blit(lbl_top, (bx + 4, 18))

    # MODULO A: CONFIGURACIÓN ACTUAL
    dibujar_modulo_propio(superficie, bx, 55, cw, 75, "Entorno y Reloj")
    superficie.blit(fnt_resaltada.render(f"Hora: {reloj_interno}", True, TEXTO_PRINCIPAL), (bx + 14, 88))
    superficie.blit(fnt_standard.render(f"Clima: {estado_clima}", True, TEXTO_SECUNDARIO), (bx + 140, 88))

    # MODULO B: CONTROLADORES AUTOMÁTICOS
    dibujar_modulo_propio(superficie, bx, 136, cw, 70, "Automatización")
    color_sw = (70, 200, 120) if flujo_activo else (100, 110, 122)
    pygame.draw.rect(superficie, color_sw, (bx + 14, 166, 38, 18), border_radius=9)
    cx = bx + 41 if flujo_activo else bx + 23
    pygame.draw.circle(superficie, (255, 255, 255), (cx, 175), 7)
    superficie.blit(fnt_standard.render("Generador de flujo continuo", True, TEXTO_PRINCIPAL), (bx + 62, 166))

    # MODULO C: INYECCIÓN MANUAL DE TRÁFICO
    dibujar_modulo_propio(superficie, bx, 212, cw, 95, "Inyección Manual de Tráfico")
    pygame.draw.rect(superficie, PANEL_FONDO, (bx + 14, 242, 120, 22), border_radius=4)
    pygame.draw.rect(superficie, BORDE_ESTRUCTURA, (bx + 14, 242, 120, 22), 1, border_radius=4)
    superficie.blit(fnt_standard.render(f"{sim_vehiculo_tipo} ▾", True, TEXTO_PRINCIPAL), (bx + 22, 244))

    pygame.draw.rect(superficie, PANEL_FONDO, (bx + 14, 270, 120, 22), border_radius=4)
    pygame.draw.rect(superficie, BORDE_ESTRUCTURA, (bx + 14, 270, 120, 22), 1, border_radius=4)
    superficie.blit(fnt_standard.render(f"{ETIQUETAS_DIRECCION[direccion_seleccionada]} ▾", True, TEXTO_PRINCIPAL), (bx + 22, 272))

    btn_inyectar = pygame.Rect(bx + 145, 270, cw - 160, 22)
    pygame.draw.rect(superficie, BORDE_ESTRUCTURA, btn_inyectar, border_radius=4)
    superficie.blit(fnt_resaltada.render("+ Despachar", True, TEXTO_PRINCIPAL), (bx + 165, 272))

    # MODULO C2: INYECCIÓN MANUAL DE PEATONES (selector y botón propios, independientes del tráfico)
    dibujar_modulo_propio(superficie, bx, 313, cw, 60, "Inyección Manual de Peatones")
    pygame.draw.rect(superficie, PANEL_FONDO, (bx + 14, 341, 120, 22), border_radius=4)
    pygame.draw.rect(superficie, BORDE_ESTRUCTURA, (bx + 14, 341, 120, 22), 1, border_radius=4)
    superficie.blit(fnt_standard.render(f"{ETIQUETAS_CRUCE[cruce_seleccionado]} ▾", True, TEXTO_PRINCIPAL), (bx + 22, 343))

    btn_peaton = pygame.Rect(bx + 145, 341, cw - 160, 22)
    pygame.draw.rect(superficie, BORDE_ESTRUCTURA, btn_peaton, border_radius=4)
    superficie.blit(fnt_resaltada.render("+ Peatón", True, TEXTO_PRINCIPAL), (bx + 168, 343))

    # MODULO D: ESTADO DE SEMÁFOROS
    dibujar_modulo_propio(superficie, bx, 379, cw, 260, "Nodos de Señalización")
    offset_y = 407
    for sem in todos_los_semaforos:
        led = (250, 40, 40) if sem.es_rojo() else ((250, 200, 0) if sem.es_amarillo() else (40, 230, 100))
        pygame.draw.circle(superficie, led, (bx + 20, offset_y + 7), 4)
        superficie.blit(fnt_mini.render(sem.id, True, TEXTO_PRINCIPAL), (bx + 35, offset_y + 2))

        color_go = (35, 95, 60) if sem.forzado == "verde" else (30, 40, 50)    # resaltado = orden activa
        pygame.draw.rect(superficie, color_go, (bx + 185, offset_y, 45, 14), border_radius=3)
        superficie.blit(fnt_mini.render("GO", True, (80, 200, 120)), (bx + 198, offset_y + 1))
        color_stop = (120, 35, 35) if sem.forzado == "rojo" else (50, 30, 30)
        pygame.draw.rect(superficie, color_stop, (bx + 235, offset_y, 45, 14), border_radius=3)
        superficie.blit(fnt_mini.render("STOP", True, (230, 80, 80)), (bx + 244, offset_y + 1))
        offset_y += 18

    # MODULO E: ESTADÍSTICAS
    dibujar_modulo_propio(superficie, bx, 649, cw, 85, "Estadísticas")
    espera_promedio = (TIEMPO_ESPERA_TOTAL_MS / 1000 / VEHICULOS_PROCESADOS) if VEHICULOS_PROCESADOS else 0.0
    superficie.blit(fnt_resaltada.render(f"{len(vehiculos)} activos", True, TEXTO_PRINCIPAL), (bx + 14, 679))
    superficie.blit(fnt_resaltada.render(f"{VEHICULOS_PROCESADOS} procesados", True, TEXTO_PRINCIPAL), (bx + 150, 679))
    superficie.blit(fnt_standard.render(f"{espera_promedio:.1f}s espera promedio", True, TEXTO_SECUNDARIO), (bx + 14, 703))
    superficie.blit(fnt_standard.render(f"{len(peatones)} peatones", True, TEXTO_SECUNDARIO), (bx + 200, 703))

    # MODULO F: TERMINAL LOG
    dibujar_modulo_propio(superficie, bx, 740, cw, 90, "Terminal Log Asíncrono")
    pygame.draw.rect(superficie, (18, 24, 30), (bx + 12, 766, cw - 24, 56), border_radius=5)
    log_y = 774
    for msg in mensajes_consola:
        superficie.blit(fnt_mini.render(msg[:45], True, (110, 160, 200)), (bx + 20, log_y))
        log_y += 18

    # Listas desplegables al final para que queden por encima de todo el resto del panel
    if dropdown_abierto == "tipo":
        for i, t in enumerate(TIPOS_DISPONIBLES):
            ry = 264 + i * 22
            rect = pygame.Rect(bx + 14, ry, 120, 22)
            pygame.draw.rect(superficie, PANEL_FONDO, rect)
            pygame.draw.rect(superficie, BORDE_ESTRUCTURA, rect, 1)
            superficie.blit(fnt_standard.render(t, True, TEXTO_PRINCIPAL), (bx + 22, ry + 2))
    elif dropdown_abierto == "direccion":
        for i, d in enumerate(DIRECCIONES_DISPONIBLES):
            ry = 292 + i * 22
            rect = pygame.Rect(bx + 14, ry, 120, 22)
            pygame.draw.rect(superficie, PANEL_FONDO, rect)
            pygame.draw.rect(superficie, BORDE_ESTRUCTURA, rect, 1)
            superficie.blit(fnt_standard.render(ETIQUETAS_DIRECCION[d], True, TEXTO_PRINCIPAL), (bx + 22, ry + 2))
    elif dropdown_abierto == "cruce":
        for i, c in enumerate(CRUCES_PEATONALES):
            ry = 363 + i * 22
            rect = pygame.Rect(bx + 14, ry, 120, 22)
            pygame.draw.rect(superficie, PANEL_FONDO, rect)
            pygame.draw.rect(superficie, BORDE_ESTRUCTURA, rect, 1)
            superficie.blit(fnt_standard.render(ETIQUETAS_CRUCE[c], True, TEXTO_PRINCIPAL), (bx + 22, ry + 2))

COLOR_POR_TIPO = {"ambulancia": (255, 255, 255), "bomberos": (200, 30, 30)}

def _retroceder(v, cantidad):
    """Mueve al vehículo hacia atrás sobre SU PROPIO eje de avance (nunca de
    lado): así jamás termina invadiendo un carril vecino, la acera o el parque."""
    if v.direccion == "derecha":     v.x -= cantidad
    elif v.direccion == "izquierda": v.x += cantidad
    elif v.direccion == "abajo":     v.y -= cantidad
    elif v.direccion == "arriba":    v.y += cantidad
 
def separar_vehiculos(a, b):
    """Separa a dos vehículos ya encimados retrocediendo a cada uno sobre su
    propio carril (nunca de lado, para respetar calles y avenidas). Es el
    último recurso cuando revertir al estado anterior no alcanza porque ya
    venían chocados desde el frame en que se originó el problema (p. ej. un
    giro o un cambio de carril simultáneo)."""
    ra, rb = a.obtener_rectangulo(), b.obtener_rectangulo()
    solape_x = min(ra.right, rb.right) - max(ra.left, rb.left)
    solape_y = min(ra.bottom, rb.bottom) - max(ra.top, rb.top)
    if solape_x <= 0 or solape_y <= 0:
        return  # ya no se tocan
    margen = 0.5  # extra para que no vuelvan a rozar por redondeo
    eje_a = "x" if a.direccion in ("derecha", "izquierda") else "y"
    eje_b = "x" if b.direccion in ("derecha", "izquierda") else "y"
    if eje_a == eje_b:
        # Mismo eje de avance (carriles gemelos o el mismo carril): cada uno
        # retrocede la mitad, como si frenaran de golpe uno detrás del otro.
        solape = solape_x if eje_a == "x" else solape_y
        paso = solape / 2 + margen
        _retroceder(a, paso)
        _retroceder(b, paso)
    else:
        # Cruce perpendicular dentro de la intersección: cada uno retrocede
        # sobre SU propio eje, lo necesario según cuánto se solapan en ese eje.
        _retroceder(a, (solape_x if eje_a == "x" else solape_y) + margen)
        _retroceder(b, (solape_x if eje_b == "x" else solape_y) + margen)
    a.velocidad = 0
    b.velocidad = 0
 
 
def spawn_peaton(nombre_cruce, todos_peatones):
    cfg = CRUCES_PEATONALES[nombre_cruce]
    sentido = random.choice([1, -1])
    if cfg["eje"] == "y":
        x, y = cfg["fijo"], (cfg["ini"] if sentido == 1 else cfg["fin"])
    else:
        x, y = (cfg["ini"] if sentido == 1 else cfg["fin"]), cfg["fijo"]
    todos_peatones.append(Peaton(x, y, cfg["eje"], sentido, semaforo=cfg["sem"],
                                  limite_ini=cfg["ini"], limite_fin=cfg["fin"]))

def spawn_seguro(direccion, todos_vehiculos, tipo_forzado=None):
    tipo = tipo_forzado or ("ambulancia" if random.random() < 0.02 else "auto")
    color_v = COLOR_POR_TIPO.get(tipo, (random.randint(70,210), random.randint(110,210), random.randint(210,255)))
    vel_v = 2.4 if tipo in ("ambulancia", "bomberos") else 1.5

    # Zona de entrada por rectángulo, extendida más allá del borde para evitar spawns apilados
    if direccion == "derecha":
        carril_y = random.choice([362, 412])
        zona = pygame.Rect(-60, carril_y - 6, 170, 34)
        if not any(zona.colliderect(v.obtener_rectangulo()) for v in todos_vehiculos):
            todos_vehiculos.append(Vehiculo(0, carril_y, 44, 22, color_v, vel_v, "derecha", [sem_c1_oeste, sem_c2_oeste, sem_c3_oeste], tipo))
    elif direccion == "izquierda":
        carril_y = random.choice([262, 312])
        zona = pygame.Rect(ANCHO_SIM - 110, carril_y - 6, 170, 34)
        if not any(zona.colliderect(v.obtener_rectangulo()) for v in todos_vehiculos):
            todos_vehiculos.append(Vehiculo(ANCHO_SIM, carril_y, 44, 22, color_v, vel_v, "izquierda", [sem_c3_este, sem_c2_este, sem_c1_este], tipo))
    elif direccion == "abajo":
        # Las tres calles reciben tráfico "abajo" por su carril derecho (norte)
        calle_x, sem_calle = random.choice([(CALLE_1_X, sem_c1_norte), (CALLE_2_X, sem_c2_norte), (CALLE_3_X, sem_c3_norte)])
        carril_x = calle_x + 84
        zona = pygame.Rect(carril_x - 6, -60, 34, 170)
        if not any(zona.colliderect(v.obtener_rectangulo()) for v in todos_vehiculos):
            todos_vehiculos.append(Vehiculo(carril_x, 0, 22, 44, color_v, vel_v, "abajo", [sem_calle], tipo))
    elif direccion == "arriba":
        # Y por su carril izquierdo (sur)
        calle_x, sem_calle = random.choice([(CALLE_1_X, sem_c1_sur), (CALLE_2_X, sem_c2_sur), (CALLE_3_X, sem_c3_sur)])
        carril_x = calle_x + 14
        zona = pygame.Rect(carril_x - 6, ALTO - 110, 34, 170)
        if not any(zona.colliderect(v.obtener_rectangulo()) for v in todos_vehiculos):
            todos_vehiculos.append(Vehiculo(carril_x, ALTO, 22, 44, color_v, vel_v, "arriba", [sem_calle], tipo))

def dibujar_parque_urbano(superficie, px, py, pw, ph):
    """Dibuja un parque verde limpio delimitado por una acera fina"""
    # Acera perimetral externa
    pygame.draw.rect(superficie, Aceras, (px, py, pw, ph), border_radius=6)
    # Interior verde de la hierba del parque
    pygame.draw.rect(superficie, Color_Hierba, (px + 4, py + 4, pw - 8, ph - 8), border_radius=4)

def dibujar_ciudad_diseno(superficie):
    # Fondo base gris oscuro (conecta las aceras)
    superficie.fill((90, 95, 98))

    # Capa de Carreteras de Asfalto Gris Puro
    pygame.draw.rect(superficie, Color_Asfalto, (0, 250, ANCHO_SIM, 200))
    pygame.draw.rect(superficie, Color_Asfalto, (CALLE_1_X, 0, 140, ALTO))
    pygame.draw.rect(superficie, Color_Asfalto, (CALLE_2_X, 0, 140, ALTO))
    pygame.draw.rect(superficie, Color_Asfalto, (CALLE_3_X, 0, 140, ALTO))

    # --- DIBUJADO DE PARQUES EN LAS MANZANAS (Sin cajas grises feas) ---
    dibujar_parque_urbano(superficie, 12, 12, CALLE_1_X - 24, 226)                           # Noroeste
    dibujar_parque_urbano(superficie, CALLE_1_X + 152, 12, CALLE_2_X - CALLE_1_X - 164, 226)  # Norte Centro-Izquierda
    dibujar_parque_urbano(superficie, CALLE_2_X + 152, 12, CALLE_3_X - CALLE_2_X - 164, 226)  # Norte Centro-Derecha
    dibujar_parque_urbano(superficie, CALLE_3_X + 152, 12, ANCHO_SIM - CALLE_3_X - 164, 226)  # Noreste

    dibujar_parque_urbano(superficie, 12, 462, CALLE_1_X - 24, 276)                           # Suroeste
    dibujar_parque_urbano(superficie, CALLE_1_X + 152, 462, CALLE_2_X - CALLE_1_X - 164, 276) # Sur Centro-Izquierda
    dibujar_parque_urbano(superficie, CALLE_2_X + 152, 462, CALLE_3_X - CALLE_2_X - 164, 276) # Sur Centro-Derecha
    dibujar_parque_urbano(superficie, CALLE_3_X + 152, 462, ANCHO_SIM - CALLE_3_X - 164, 276) # Sureste

    # Árboles con copa sombreada de dos tonalidades para mayor detalle estético
    for ax, ay, r in arboles_parques:
        # Tronco
        pygame.draw.rect(superficie, Color_Tronco, (ax - 2, ay + r - 3, 4, r // 2 + 4))
        # Sombra base de las hojas
        pygame.draw.circle(superficie, Color_Hojas, (ax, ay), r)
        # Brillo superior de las hojas
        pygame.draw.circle(superficie, Color_Hojas_Luz, (ax - 2, ay - 2), r - 3)

    # Líneas viales divisorias amarillas
    pygame.draw.line(superficie, Color_Amarillo_Vial, (0, 350), (CALLE_1_X, 350), 3)
    pygame.draw.line(superficie, Color_Amarillo_Vial, (CALLE_1_X + 140, 350), (CALLE_2_X, 350), 3)
    pygame.draw.line(superficie, Color_Amarillo_Vial, (CALLE_2_X + 140, 350), (CALLE_3_X, 350), 3)
    pygame.draw.line(superficie, Color_Amarillo_Vial, (CALLE_3_X + 140, 350), (ANCHO_SIM, 350), 3)

    # Líneas de carriles discontinuas blancas
    for x in range(0, ANCHO_SIM, 40):
        if (CALLE_1_X <= x <= CALLE_1_X + 140) or (CALLE_2_X <= x <= CALLE_2_X + 140) or (CALLE_3_X <= x <= CALLE_3_X + 140): continue
        pygame.draw.line(superficie, (255, 255, 255), (x, 300), (x + 15, 300), 2)
        pygame.draw.line(superficie, (255, 255, 255), (x, 400), (x + 15, 400), 2)

    for cx in [CALLE_1_X, CALLE_2_X, CALLE_3_X]:
        pygame.draw.line(superficie, Color_Amarillo_Vial, (cx + 70, 0), (cx + 70, 250), 2)
        pygame.draw.line(superficie, Color_Amarillo_Vial, (cx + 70, 450), (cx + 70, ALTO), 2)

    # Flechas de sentido por carril en el boulevard (como en el simulador de referencia)
    for fx in range(120, ANCHO_SIM - 60, 160):
        if (CALLE_1_X - 60 <= fx <= CALLE_1_X + 160) or (CALLE_2_X - 60 <= fx <= CALLE_2_X + 160) or (CALLE_3_X - 60 <= fx <= CALLE_3_X + 160): continue
        for fy in (273, 323):   # carriles hacia la izquierda
            pygame.draw.polygon(superficie, (150, 155, 160), [(fx + 8, fy - 4), (fx + 8, fy + 4), (fx, fy)])
        for fy in (373, 423):   # carriles hacia la derecha
            pygame.draw.polygon(superficie, (150, 155, 160), [(fx, fy - 4), (fx, fy + 4), (fx + 8, fy)])

    # Cebras Peatonales
    for i in range(4): pygame.draw.rect(superficie, Color_Cebra, (CALLE_1_X - 18, 255 + (i * 50), 14, 26))
    for i in range(4): pygame.draw.rect(superficie, Color_Cebra, (CALLE_1_X + 8 + (i * 34), 453, 24, 14))
    for i in range(4): pygame.draw.rect(superficie, Color_Cebra, (CALLE_1_X + 8 + (i * 34), 231, 24, 14))
    for i in range(4): pygame.draw.rect(superficie, Color_Cebra, (CALLE_2_X - 18, 255 + (i * 50), 14, 26))
    for i in range(4): pygame.draw.rect(superficie, Color_Cebra, (CALLE_2_X + 8 + (i * 34), 231, 24, 14))
    for i in range(4): pygame.draw.rect(superficie, Color_Cebra, (CALLE_2_X + 8 + (i * 34), 453, 24, 14))
    for i in range(4): pygame.draw.rect(superficie, Color_Cebra, (CALLE_3_X - 18, 255 + (i * 50), 14, 26))
    for i in range(4): pygame.draw.rect(superficie, Color_Cebra, (CALLE_3_X + 8 + (i * 34), 231, 24, 14))
    for i in range(4): pygame.draw.rect(superficie, Color_Cebra, (CALLE_3_X + 8 + (i * 34), 453, 24, 14))

    # --- SEÑALIZACIONES VIALES Y TEXTOS DE IDENTIDAD ---
    color_txt_vial = (210, 215, 220)
    
    # Textos de Carril Orientativo
    superficie.blit(fnt_vial.render("ENT-O ──>", True, color_txt_vial), (25, 365))
    superficie.blit(fnt_vial.render("SAL-E ──>", True, color_txt_vial), (ANCHO_SIM - 100, 365))
    superficie.blit(fnt_vial.render("<── ENT-E", True, color_txt_vial), (ANCHO_SIM - 105, 315))

    # Flechas Directas sobre el Asfalto (ambas calles de doble sentido: carril izq. sube, carril der. baja)
    for calle_x in (CALLE_1_X, CALLE_2_X, CALLE_3_X):
        superficie.blit(fnt_vial.render("↑", True, Color_Cebra), (calle_x + 8, 70))
        superficie.blit(fnt_vial.render("↑", True, Color_Cebra), (calle_x + 8, ALTO - 90))
        superficie.blit(fnt_vial.render("↓", True, Color_Cebra), (calle_x + 98, 70))
        superficie.blit(fnt_vial.render("↓", True, Color_Cebra), (calle_x + 98, ALTO - 90))

# --- BUCLE OPERATIVO PRINCIPAL ---
while True:
    tiempo_actual = pygame.time.get_ticks()
    dt = tiempo_actual - PREV_TICK
    PREV_TICK = tiempo_actual

    for evento in pygame.event.get():
        if evento.type == pygame.QUIT:
            pygame.quit()
            sys.exit()
            
        if evento.type == pygame.MOUSEBUTTONDOWN:
            mx, my = evento.pos
            if dropdown_abierto == "tipo":
                for i, t in enumerate(TIPOS_DISPONIBLES):
                    ry = 264 + i * 22
                    if ANCHO_SIM + 14 <= mx <= ANCHO_SIM + 134 and ry <= my <= ry + 22:
                        sim_vehiculo_tipo = t
                dropdown_abierto = None
            elif dropdown_abierto == "direccion":
                for i, d in enumerate(DIRECCIONES_DISPONIBLES):
                    ry = 292 + i * 22
                    if ANCHO_SIM + 14 <= mx <= ANCHO_SIM + 134 and ry <= my <= ry + 22:
                        direccion_seleccionada = d
                dropdown_abierto = None
            elif dropdown_abierto == "cruce":
                for i, c in enumerate(CRUCES_PEATONALES):
                    ry = 363 + i * 22
                    if ANCHO_SIM + 14 <= mx <= ANCHO_SIM + 134 and ry <= my <= ry + 22:
                        cruce_seleccionado = c
                dropdown_abierto = None
            elif ANCHO_SIM + 14 <= mx <= ANCHO_SIM + 52 and 166 <= my <= 184:
                flujo_activo = not flujo_activo
            elif ANCHO_SIM + 14 <= mx <= ANCHO_SIM + 134 and 242 <= my <= 264:
                dropdown_abierto = "tipo"
            elif ANCHO_SIM + 14 <= mx <= ANCHO_SIM + 134 and 270 <= my <= 292:
                dropdown_abierto = "direccion"
            elif ANCHO_SIM + 145 <= mx <= ANCHO_TOTAL - 15 and 270 <= my <= 292:
                tipo_forzado = sim_vehiculo_tipo.lower() if sim_vehiculo_tipo != "Auto" else None
                spawn_seguro(direccion_seleccionada, vehiculos, tipo_forzado=tipo_forzado)
            elif ANCHO_SIM + 14 <= mx <= ANCHO_SIM + 134 and 341 <= my <= 363:
                dropdown_abierto = "cruce"
            elif ANCHO_SIM + 145 <= mx <= ANCHO_TOTAL - 15 and 341 <= my <= 363:
                spawn_peaton(cruce_seleccionado, peatones)
            else:
                # Botones GO/STOP por semáforo
                for i, s in enumerate(todos_los_semaforos):
                    ry = 407 + i * 18
                    if ry <= my <= ry + 14:
                        if ANCHO_SIM + 197 <= mx <= ANCHO_SIM + 242:   # GO (toggle): fuerza verde coordinado
                            if s.forzado == "verde":
                                s.forzado = None  # segundo click: vuelve al automático
                            else:
                                s.forzado = "verde"
                                # Solo un GO por cruce: revoca el del rival perpendicular
                                for otro in (cruce_1 if s in cruce_1 else cruce_2):
                                    if otro is not s and otro.direccion != s.direccion and otro.forzado == "verde":
                                        otro.forzado = None
                        elif ANCHO_SIM + 247 <= mx <= ANCHO_SIM + 292:  # STOP (toggle): congelado en rojo
                            s.forzado = None if s.forzado == "rojo" else "rojo"

    while not cola_sensores.empty():
        direccion, tipo = cola_sensores.get()
        spawn_seguro(direccion, vehiculos, tipo_forzado=tipo)

    if flujo_activo and tiempo_actual - ULTERIOR_SPAWN >= INTERVALO_SPAWN:
        dir_rand = random.choice(["derecha", "izquierda", "abajo", "arriba"])
        spawn_seguro(dir_rand, vehiculos)
        ULTERIOR_SPAWN = tiempo_actual

    restantes = []
    for v in vehiculos:
        if -80 <= v.x <= ANCHO_SIM + 80 and -80 <= v.y <= ALTO + 80:
            restantes.append(v)
        else:
            VEHICULOS_PROCESADOS += 1
            TIEMPO_ESPERA_TOTAL_MS += v.tiempo_esperando
    vehiculos = restantes
    peatones = [p for p in peatones if not p.fuera_de_pantalla(ANCHO_SIM, ALTO)]
    for p in peatones:
        p.mover(vehiculos)

    # Estado seguro de cada vehículo ANTES de moverse este frame (por invariante,
    # en este punto nunca hay dos vehículos solapados: el frame anterior ya
    # terminó limpio gracias a la red de seguridad de más abajo).
    estados_previos = {v: v.snapshot() for v in vehiculos}

    for v in vehiculos:
        if v.puede_avanzar(vehiculos, peatones, calles_x=(CALLE_1_X, CALLE_2_X, CALLE_3_X)):
            v.mover(ANCHO_SIM, ALTO, CALLE_1_X, CALLE_2_X, todos_los_semaforos, vehiculos)
        if v.velocidad == 0:
            v.tiempo_esperando += dt

    # --- RED DE SEGURIDAD FINAL ANTI-CHOQUES ---
    # Con tráfico saturado pueden coincidir casos límite que la lógica de
    # "puede_avanzar" no cubre del todo (giros, dos autos cambiándose de carril
    # a la vez, etc.). Primero se intenta revertir al último estado seguro.
    # Pero si ese estado anterior YA venía encimado (el choque no se originó
    # en este frame, sino en el momento exacto de un giro o cambio de carril),
    # revertir no sirve de nada -en ese caso se separan físicamente empujando
    # cada vehículo en direcciones opuestas hasta que dejan de tocarse. Así
    # nunca queda un par "congelado" chocando en pantalla.
    for _ in range(len(vehiculos) + 2):
        hubo_conflicto = False
        for i, a in enumerate(vehiculos):
            for b in vehiculos[i + 1:]:
                if a.obtener_rectangulo().colliderect(b.obtener_rectangulo()):
                    log_choques.info(
                        f"{a.tipo}/{a.direccion}@({a.x:.1f},{a.y:.1f}) vs "
                        f"{b.tipo}/{b.direccion}@({b.x:.1f},{b.y:.1f}) -> revertido"
                    )
                    a.restaurar(estados_previos[a])
                    b.restaurar(estados_previos[b])
                    if a.obtener_rectangulo().colliderect(b.obtener_rectangulo()):
                        # Ya venían encimados antes de moverse: no hay estado
                        # previo "sano" al cual volver, así que se separan a la fuerza.
                        separar_vehiculos(a, b)
                        log_choques.info(
                            f"{a.tipo}/{a.direccion}@({a.x:.1f},{a.y:.1f}) vs "
                            f"{b.tipo}/{b.direccion}@({b.x:.1f},{b.y:.1f}) -> separados a la fuerza"
                        )
                    hubo_conflicto = True
        if not hubo_conflicto:
            break

    # Carril de giro aglomerado presiona al semáforo de frente para ceder antes
    sem_c1_este.rival_urgente = sem_c1_oeste.cola_giro >= 2 or sem_c1_oeste.tiempo_espera_giro >= 3000
    sem_c2_oeste.rival_urgente = sem_c2_este.cola_giro >= 2 or sem_c2_este.tiempo_espera_giro >= 3000

    for sem in cruce_1:
        sem.actualizar_inteligente(vehiculos, cruce_1, CAJA_CRUCE_1, peatones=peatones)
    for sem in cruce_2:
        sem.actualizar_inteligente(vehiculos, cruce_2, CAJA_CRUCE_2, peatones=peatones)
    for sem in cruce_3:
        sem.actualizar_inteligente(vehiculos, cruce_3, CAJA_CRUCE_3, peatones=peatones)

    # 4ta luz: solo verde si no hay tráfico rival y la caja está despejada
    sem_c1_oeste.flecha_verde = sem_c1_este.es_rojo() and sem_c1_sur.es_rojo() and not any(v.obtener_rectangulo().colliderect(CAJA_CRUCE_1) for v in vehiculos)
    sem_c2_este.flecha_verde = sem_c2_oeste.es_rojo() and sem_c2_norte.es_rojo() and not any(v.obtener_rectangulo().colliderect(CAJA_CRUCE_2) for v in vehiculos)

    # Dibujado Capa por Capa
    dibujar_ciudad_diseno(pantalla)

    for sem in todos_los_semaforos: sem.dibujar_sensor(pantalla)
    for sem in todos_los_semaforos: sem.dibujar(pantalla)
    for v in vehiculos: v.dibujar(pantalla)
    for p in peatones: p.dibujar(pantalla)

    dibujar_original_sidebar(pantalla)

    pygame.display.flip()
    clock.tick(60)
 
 
 























