import pygame as pg

pg.joystick.init()

num_joysticks = pg.joystick.get_count()

print(num_joysticks)