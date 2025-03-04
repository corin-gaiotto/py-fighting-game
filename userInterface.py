import pygame as pg
import pygame.gfxdraw as gfx
import math


def worldToScreen(screen, posn):
    # changes a world position (x or y) to a screen position (x or y) while preserving world aspect ratio
    x_scale = screen.get_size()[0]/456
    y_scale = screen.get_size()[1]/256
    scale = min(x_scale, y_scale)
    return posn*scale

def x_worldToScreen(screen, posn):
    # changes a world xpos to a screen xpos while preserving world aspect ratio and centering
    x_scale = screen.get_size()[0]/456
    y_scale = screen.get_size()[1]/256
    scale = min(x_scale, y_scale)
    return posn*scale + 456*(x_scale - scale)/2

def y_worldToScreen(screen, posn):
    # changes a world ypos to a screen ypos while preserving world aspect ratio and centering
    x_scale = screen.get_size()[0]/456
    y_scale = screen.get_size()[1]/256
    scale = min(x_scale, y_scale)
    return posn*scale + 256*(y_scale - scale)/2

def rect_worldToScreen(screen, rect):
    return pg.Rect(x_worldToScreen(screen, rect.left), y_worldToScreen(screen, rect.top), worldToScreen(screen, rect.width), worldToScreen(screen, rect.height))


class Timer:
    def __init__(self, posx, posy):
        self.posx = posx
        self.posy = posy
        self.font = pg.font.SysFont("dejavusansmono", 18)
    def draw(self, time, screen):
        render = self.font.render(str(time//30),True,(0,0,0))
        rect = render.get_rect()
        rect.center = self.posx, self.posy
        screen.blit(render, rect_worldToScreen(screen, rect))

class ScoreIndicator:
    def __init__(self, posx, posy, inverted):
        self.posx = posx
        self.posy = posy
        self.inverted = inverted
    def draw(self, level, screen):
        for i in range(2):
            if level > i:
                colour = (255,100,0)
            else:
                colour = (50,50,50)
            pg.draw.circle(screen, colour, (x_worldToScreen(screen,self.posx+16*i*(-1 if self.inverted else 1)), y_worldToScreen(screen,self.posy)), worldToScreen(screen,8))
class ChargeLevel:
    def __init__(self, posx, posy, inverted):
        self.posx = posx
        self.posy = posy
        self.inverted = inverted
    def draw(self, level, screen):
        for i in range(5):
            if level > i:
                colour = (180,0,180)
            else:
                colour = (50,0,50)
            pg.draw.circle(screen, colour, (x_worldToScreen(screen,self.posx+8*i*(-1 if self.inverted else 1)), (y_worldToScreen(screen,self.posy))), worldToScreen(screen,4))


class HoverText:
    def __init__(self, text, posx, posy, size, colour, time):
        self.text = text
        self.posx = posx
        self.posy = posy
        self.colour = colour
        self.font = pg.font.SysFont("dejavusansmono", size)
        self.time = time
    def draw(self, screen):
        if self.time > 0:
            render = self.font.render(self.text,True,self.colour)
            rect = render.get_rect()
            rect.center = self.posx, self.posy
            screen.blit(render, rect_worldToScreen(screen, rect))
        self.time -= 1

class InstallTimer:
    def __init__(self, posx, posy, inverted, colour):
        self.posx = posx
        self.posy = posy
        self.inverted = inverted
        self.colour = colour
    def draw(self, amount, screen):
        if self.inverted:
            pg.draw.rect(screen, self.colour, rect_worldToScreen(screen, pg.Rect(self.posx+75-amount/4, self.posy, amount/4, 8)))
        else:
            pg.draw.rect(screen, self.colour, rect_worldToScreen(screen, pg.Rect(self.posx, self.posy, amount/4, 8)))
class FilledBar:
    def __init__(self, posx, posy, length, height, inverted, emptyColour, filledColour, specialColour=(0,0,0), specialThreshold=1.1):
        self.posx = posx
        self.posy = posy
        self.length = length
        self.height = height
        self.inverted = inverted
        self.emptyColour = emptyColour
        self.filledColour = filledColour
        self.specialColour = specialColour
        self.specialThreshold = specialThreshold
    def draw(self, amount, maxAmount, screen):
        pg.draw.rect(screen, self.emptyColour, rect_worldToScreen(screen, pg.Rect(self.posx, self.posy, self.length, self.height)))
        fillAmount = math.ceil(self.length*amount/maxAmount)
        if amount/maxAmount >= self.specialThreshold:
            colour = self.specialColour
        else:
            colour = self.filledColour
        if self.inverted:
            pg.draw.rect(screen, colour, rect_worldToScreen(screen, pg.Rect(self.posx+self.length-fillAmount, self.posy, fillAmount, self.height)))
        else:
            pg.draw.rect(screen, colour, rect_worldToScreen(screen, pg.Rect(self.posx, self.posy, fillAmount, self.height)))

class ComboCounter:
    def __init__(self, posx, posy):
        self.currentMax = 0
        self.timeVisible = 0
        self.posx = posx
        self.posy = posy
        self.bigFont = pg.font.SysFont("OpenSans Mono", 180, True, False)
    def Update(self, screen, comboCount):
        if comboCount != 0:
            self.currentMax = comboCount
            self.timeVisible = 45
        if self.timeVisible > 0 and self.currentMax > 1:
            # draw self
            self.draw(screen)
        else:
            self.currentMax = comboCount
        self.timeVisible -= 1
    def draw(self, screen):
        render = self.bigFont.render(str(self.currentMax),True,(0,0,0))
        render.set_alpha(80)
        x_scale = screen.get_size()[0]/456
        y_scale = screen.get_size()[1]/256
        scale = min(x_scale, y_scale)
        #print(x_scale, y_scale, scale)
        render = pg.transform.scale_by(render, (1 + self.timeVisible**2/8100)*scale)
        rect = render.get_rect() 
        rect.center = x_worldToScreen(screen, self.posx), y_worldToScreen(screen, self.posy)
        screen.blit(render, rect)