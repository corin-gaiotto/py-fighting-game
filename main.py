import pygame as pg
import gameLogic
import userInterface
import inputHelp

# CONFIG: turn on to access training mode/combo trials
TRAININGMODE = True

# 456x256 is base
screen = pg.display.set_mode((456,256))
clock = pg.time.Clock()

pg.font.init()

data = gameLogic.DataReader.readAllCharData(["character1", "dehya", "raiden", "venti", "xiao", "bennett", "navia", "childe", "zhongli", "ayaka", "wriothesley", "kaveh", "marionette"])

gameManager = gameLogic.GameManager(screen, TRAININGMODE)



while 1:
    screen.fill((0,0,0))
    inputs = pg.key.get_pressed()
    if inputs[pg.K_1]:
        screen = pg.display.set_mode((1920,1080))
        gameManager.reset_font_size(screen)
    elif inputs[pg.K_2]:
        screen = pg.display.set_mode((456,256))
        gameManager.reset_font_size(screen)
    gameManager.Update(inputs, screen)
    
    pg.display.flip()
    pg.event.pump()
    clock.tick(30)