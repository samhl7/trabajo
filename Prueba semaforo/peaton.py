import pygame

class Peaton:
    def __init__(self, x, y, eje, sentido, semaforo=None, limite_ini=None, limite_fin=None,
                 velocidad=0.8, color=(250, 200, 60)):
        self.x = x
        self.y = y
        self.eje = eje          # "x" o "y"
        self.sentido = sentido  # 1 o -1
        self.semaforo = semaforo  # None = cruce libre
        self.limite_ini = limite_ini  # borde de la calzada
        self.limite_fin = limite_fin
        self.velocidad = velocidad
        self.color = color
        self.cruzando = False  # ya no se detiene a mitad de calle

    def puede_caminar(self):
        # Si ya cruza sigue derecho; si no, espera semáforo en rojo
        return self.cruzando or self.semaforo is None or self.semaforo.es_rojo()

    def en_la_calle(self):
        # ¿sigue dentro de la calzada?
        if self.limite_ini is None:
            return False
        pos = self.x if self.eje == "x" else self.y
        return self.limite_ini <= pos <= self.limite_fin

    def mover(self, vehiculos=()):
        if not self.puede_caminar():
            return
        nx, ny = self.x, self.y
        if self.eje == "x":
            nx += self.velocidad * self.sentido
        else:
            ny += self.velocidad * self.sentido
        # No atraviesa carros
        cuerpo = pygame.Rect(nx - 6, ny - 6, 12, 18)
        if any(cuerpo.colliderect(v.obtener_rectangulo()) for v in vehiculos):
            return
        self.cruzando = True
        self.x, self.y = nx, ny

    def dibujar(self, pantalla):
        pygame.draw.circle(pantalla, (20, 20, 20), (int(self.x), int(self.y) + 5), 4)  # sombra/cuerpo
        pygame.draw.circle(pantalla, self.color, (int(self.x), int(self.y)), 4)         # cabeza

    def fuera_de_pantalla(self, ancho, alto):
        return not (-20 <= self.x <= ancho + 20 and -20 <= self.y <= alto + 20)
