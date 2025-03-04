import json
import os
from types import MethodDescriptorType
import pygame as pg
import userInterface
from collections import deque
import math

def worldToScreen(screen, posn):
    # changes a world value to a screen value while preserving world aspect ratio
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

def font_worldToScreen(screen, sz):
    x_scale = screen.get_size()[0]/456
    y_scale = screen.get_size()[1]/256
    scale = min(x_scale, y_scale)
    return int(math.ceil(sz*(1 + scale)/2))

def rect_worldToScreen(screen, rect):
    return pg.Rect(x_worldToScreen(screen, rect.left), y_worldToScreen(screen, rect.top), worldToScreen(screen, rect.width), worldToScreen(screen, rect.height))

def clamp(x, xmin, xmax):
    return min(max(x,xmin),xmax)
def drawTransparentBox(screen, colour, rect):
    rect = rect_worldToScreen(screen, rect)
    temp = pg.Surface(pg.Rect(rect).size, pg.SRCALPHA)
    pg.draw.rect(temp, colour, temp.get_rect())
    screen.blit(temp, rect)

class Box:
    def __init__(self, left, top, length, height, active):
        self.left = left
        self.top = top
        self.length = length
        self.height = height
        self.active = active
    def horizontalReflection(self, axis):
        rightmost = self.left+self.length
        newLeftmost = 2*axis - rightmost
        return Box(newLeftmost,self.top,self.length,self.height,self.active)
    def translate(self, x, y):
        return Box(self.left+x,self.top+y,self.length,self.height,self.active)
    def connectedCollide(self, other, selfX, selfY, otherX, otherY):
        if (self.active and other.active):
            collX = self.left+selfX + self.length >= other.left+otherX and other.left+otherX + other.length >= self.left+selfX
            collY = self.top+selfY + self.height >= other.top+otherY and other.top+otherY + other.height >= self.top+selfY
            return (collX and collY)
        return False
    def collide(self, other):
        if (self.active and other.active):
            collX = self.left + self.length >= other.left and other.left + other.length >= self.left
            collY = self.top + self.height >= other.top and other.top + other.height >= self.top
            return (collX and collY)
        return False
    def connectedDebugDraw(self, colour, screen, selfX, selfY):
        drawTransparentBox(screen, colour, pg.Rect(self.left+selfX, self.top+selfY, self.length, self.height))

    def debugDraw(self, colour, screen):
        drawTransparentBox(screen, colour, pg.Rect(self.left, self.top, self.length, self.height))

class Hurtbox(Box):
    def horizontalReflection(self, axis):
        rightmost = self.left+self.length
        newLeftmost = 2*axis - rightmost
        return Hurtbox(newLeftmost,self.top,self.length,self.height,self.active)

class PassiveBox(Box):
    def __init__(self,box, allyInstall):
        self.left = box.left
        self.top = box.top
        self.length = box.length
        self.height = box.height
        self.active = box.active

        self.allyInstall = allyInstall
    def horizontalReflection(self, axis):
        return PassiveBox(super().horizontalReflection(axis),self.allyInstall)


class Hitbox(Box):
    def __init__(self,box, damage,hitstun,blockstun,blockType, inescapable, uncomboable, grounded, knockdownType, enemyBlockX, enemyBlockY, playerBlockX, playerBlockY, enemyHitX, enemyHitY, playerHitX, playerHitY, auxiliary=False, hitnum=None):
        self.left = box.left
        self.top = box.top
        self.length = box.length
        self.height = box.height
        self.active = box.active

        self.damage = damage
        self.hitstun = hitstun
        self.blockstun = blockstun
        self.blockType = blockType

        self.inescapable = inescapable
        self.uncomboable = uncomboable
        self.grounded = grounded
        self.knockdownType = knockdownType

        self.enemyBlockX = enemyBlockX
        self.enemyBlockY = enemyBlockY
        self.playerBlockX = playerBlockX
        self.playerBlockY = playerBlockY
        
        self.enemyHitX = enemyHitX
        self.enemyHitY = enemyHitY
        self.playerHitX = playerHitX
        self.playerHitY = playerHitY

        self.auxiliary = auxiliary # tracks if attack was initiated by auxiliary, used to determine who hit, and thus which meter gain/cancels should apply
        
        self.hitnum = hitnum
    def horizontalReflection(self, axis):
        return Hitbox(super().horizontalReflection(axis),self.damage,self.hitstun,self.blockstun,self.blockType, self.inescapable, self.uncomboable, self.grounded, self.knockdownType, -self.enemyBlockX, self.enemyBlockY, -self.playerBlockX, self.playerBlockY, -self.enemyHitX, self.enemyHitY, -self.playerHitX, self.playerHitY, auxiliary=self.auxiliary, hitnum=self.hitnum)
    def translate(self, x, y):
        return Hitbox(super().translate(x,y),self.damage,self.hitstun,self.blockstun,self.blockType,self.inescapable,self.uncomboable,self.grounded,self.knockdownType,self.enemyBlockX,self.enemyBlockY,self.playerBlockX,self.playerBlockY,self.enemyHitX,self.enemyHitY,self.playerHitX,self.playerHitY, auxiliary=self.auxiliary, hitnum=self.hitnum)

class FrameData:
    def __init__(self, auxiliaryAttack, minActive, maxActive, hitboxList, hurtboxList, projectile, installData, chargeData, auxiliaryData, selfHealth, selfMeter, defaultActive, velxOverride=None, velyOverride=None):
        # controls whether or not point of reference is own position or auxiliary's position
        self.auxiliaryAttack = auxiliaryAttack
        self.minActive = minActive
        self.maxActive = maxActive
        self.hitboxList = hitboxList
        self.hurtboxList = hurtboxList
        self.projectile = projectile
        self.installData = installData
        self.chargeData = chargeData
        # controls various actions pertaining to auxiliary, such as summoning/desummoning
        self.auxiliaryData = auxiliaryData
        self.selfHealth = selfHealth
        self.selfMeter = selfMeter
        self.defaultActive = defaultActive
        self.velxOverride = velxOverride
        self.velyOverride = velyOverride

class ProjectileData:
    def __init__(self, lifetime, maxHits, hitCooldown, hitboxList, hurtboxList, passiveBoxList, velx, vely, accelx, accely):
        self.lifetime = lifetime
        self.maxHits = maxHits
        self.hitCooldown = hitCooldown
        self.hitboxList = hitboxList
        self.hurtboxList = hurtboxList
        self.passiveBoxList = passiveBoxList
        self.velx = velx
        self.vely = vely
        self.accelx = accelx
        self.accely = accely
    def createProjectile(self, inverted, posx, posy):
        return Projectile(self, self.lifetime, self.maxHits, self.hitCooldown, posx, posy, self.velx*(-1 if inverted else 1), self.vely, self.accelx*(-1 if inverted else 1), self.accely)
    

class Projectile:
    def __init__(self, data, lifetime, remainingHits, hitCooldown, posx, posy, velx, vely, accelx, accely):
        self.data = data
        self.lifetime = lifetime
        self.remainingHits = remainingHits
        self.hitCooldown = hitCooldown
        self.timeTillHit = 0
        self.posx = posx
        self.posy = posy
        self.velx = velx
        self.vely = vely
        self.accelx = accelx
        self.accely = accely
        self.hurtboxes = []
        self.hitboxes = []
    def Update(self, boxViewScreen=False):
        # TODO: projectile collision with other projectiles
        self.hurtboxes = []
        self.hitboxes = []
        if self.lifetime > 0 and self.remainingHits > 0:
            self.posx += self.velx
            self.posy += self.vely
            self.velx += self.accelx
            self.vely += self.accely
            self.hurtboxes = self.data.hurtboxList
            if self.timeTillHit < 1:
                self.hitboxes = self.data.hitboxList
            self.passiveboxes = self.data.passiveBoxList
            if boxViewScreen:
                for hurtbox in self.hurtboxes:
                    hurtbox.connectedDebugDraw((0,255,255,128),boxViewScreen, self.posx, self.posy)
                for hitbox in self.hitboxes:
                    hitbox.connectedDebugDraw((255,0,0,128),boxViewScreen, self.posx, self.posy)
                for passivebox in self.passiveboxes:
                    passivebox.connectedDebugDraw((128,0,128,64),boxViewScreen, self.posx, self.posy)
            self.lifetime -= 1
            self.timeTillHit -= 1

class Attack:
    def __init__(self, actionableAt, specialFall, moving, whiffGain, hitGain, freezing, frameDataList, meterCost=0):
        self.actionableAt = actionableAt
        self.specialFall = specialFall
        self.moving = moving
        self.whiffGain = whiffGain
        self.hitGain = hitGain
        self.freezing = freezing
        self.frameDataList = frameDataList
        self.meterCost = meterCost
    def getActiveList(self, defaultBoxes, frameTimer):
        hitboxes = []
        hurtboxes = []
        projectile = None
        installData = None
        auxiliaryData = None
        auxiliaryAttack = False
        chargeData = 0
        selfHealth = 0
        selfMeter = 0
        for frameData in self.frameDataList:
            if frameData.minActive <= frameTimer <= frameData.maxActive:
                auxiliaryAttack = frameData.auxiliaryAttack
                hitboxes += frameData.hitboxList
                hurtboxes += frameData.hurtboxList
                projectile = frameData.projectile
                installData = frameData.installData
                chargeData = frameData.chargeData
                auxiliaryData = frameData.auxiliaryData
                selfHealth = frameData.selfHealth
                selfMeter = frameData.selfMeter
                if frameData.defaultActive and not(auxiliaryAttack):
                    hurtboxes.append(defaultBoxes["standing"])
                return auxiliaryAttack, hitboxes, hurtboxes, projectile, installData, chargeData, auxiliaryData, selfHealth, selfMeter
        hurtboxes.append(defaultBoxes["standing"])
        return auxiliaryAttack, hitboxes, hurtboxes, projectile, installData, chargeData, auxiliaryData, selfHealth, selfMeter
    def getVelocity(self, inverted, frameTimer):
        for frameData in self.frameDataList:
            if frameData.minActive <= frameTimer <= frameData.maxActive:
                if frameData.velxOverride is not None or frameData.velyOverride is not None:
                    return frameData.velxOverride*(-1 if inverted else 1), frameData.velyOverride
        return None, None

class CharacterData:
    def __init__(self, name, walkSpeed, maxHealth, midairJumps, jumpVelocity, jumpDecel, jumpMin, jumpTime, fallAccel, terminalFall, defaultHurtboxes, attackDict, inputDict, projectileDict, attackGroups, auxiliaryName, auxiliaryAutoSummonTime, auxiliaryHurtboxes):
        self.name = name
        self.walkSpeed = walkSpeed
        self.maxHealth = maxHealth
        self.midairJumps = midairJumps
        self.jumpVelocity = jumpVelocity
        self.jumpDecel = jumpDecel
        self.jumpMin = jumpMin
        self.jumpTime = jumpTime
        self.fallAccel = fallAccel
        self.terminalFall = terminalFall
        self.defaultHurtboxes = defaultHurtboxes
        self.attackDict = attackDict
        self.inputDict = inputDict
        self.projectileDict = projectileDict
        self.attackGroups = attackGroups
        # name is used for special case of auxiliary being controlled by movement
        self.auxiliaryName = auxiliaryName
        self.auxiliaryAutoSummonTime = auxiliaryAutoSummonTime
        self.auxiliaryHurtboxes = auxiliaryHurtboxes

class Character:
    def __init__(self, characterData, posx, posy, health, defaultColour=(0,255,0,128)):
        """
        STATES:
            grounded_idle: default. can go into pretty much any other.
            jumping: default when rising in the air.
            air_idle: default when in the air.
            attack: in the middle of an attack. Ends when hit or when attack finishes
            block: in the middle of blockstun. Ends after timer
            hit: in the middle of hitstun. Ends after timer
        """
        self.characterData = characterData
        self.posx = posx
        self.posy = posy
        self.velx = 0
        self.vely = 0
        self.health = health
        self.defaultColour = defaultColour
        self.state = "grounded_idle"
        self.currentAttack = "" # used when state is "attack"
        self.stateTime = 0
        self.superFlash = 0
        self.hitStop = 0
        # for installs
        self.installName = None
        self.installTime = 0
        # for childe
        self.chargeLevel = 0
        # for auxiliary element (traps, puppets, etc.)
        self.auxiliaryActive = False
        self.auxiliaryTime = 0 # time till auxiliary is automatically summoned at own position, auxiliary is not auto summoned if characterData.auxiliaryAutoSummon is False
        self.auxiliaryPosX = posx
        self.auxiliaryPosY = posy
        self.auxiliaryInverted = False # facing direction
        self.auxiliaryCurrentAttack = ""
        self.auxiliaryAttackTime = 0
        
        self.nextKnockdown = None # when landing on ground, transitions to respective knockdown state
        self.hitboxes = []
        self.hurtboxes = []
        self.inverted = False # facing direction
        self.inputBuffer = deque([(["5"])]*30)
        self.currentMoveID = 0
        self.hitByID = None
        self.hitByIndexes = []
        self.comboedCounter = 0
        self.comboDamage = 0
        self.cancellableMoves = []
        self.hitThisFrame = False
        self.wasHitThisFrame = False
        self.blockedThisFrame = False
        self.connectedThisFrame = False
        self.consecutiveBounces = 0
        self.doubleJump = characterData.midairJumps
        self.jumpCancel = False
        self.superMeter = 0 # maxes out at 10000
        self.maxMeter = 10000
        self.jumpReleased = True
    def resetState(self):
        """Resets the character state to whatever the equivalent idle would be."""
        if self.posy < 200:
            if self.state != "special_fall":
                self.state = "air_idle"
        else:
            if self.posy > 200:
                self.posy = 200
            self.vely = 0
            self.state = "grounded_idle"
            self.jumpReleased = True
    def checkInput(self, bufferLength=4):
        usable = {name:data for name, data in self.characterData.inputDict.items() if data.priority}
        for name, attackInput in sorted(usable.items(), key=lambda x:x[1].priority, reverse=True):
            if self.checkAttackInput(list(reversed(attackInput.motion)),bufferLength=bufferLength) and self.characterData.attackDict[name].meterCost <= self.superMeter:
                # check install status and charge
                if (not(attackInput.requiredInstall) or (attackInput.requiredInstall and attackInput.requiredInstall == self.installName))\
                and (not(attackInput.requiredCharge) or (attackInput.requiredCharge and attackInput.requiredCharge <= self.chargeLevel))\
                and (not(attackInput.requiredAuxiliary) or (attackInput.requiredAuxiliary and self.auxiliaryActive)):
                    if attackInput.auxiliaryAttack:
                        # if auxiliary is active and free to attack (no required state)
                        if self.auxiliaryActive and self.auxiliaryCurrentAttack == "":
                            return name, True
                    else:
                        # check character state, etc.
                        if self.state in attackInput.usableStates and not(attackInput.onlyCancel):
                            return name, False
                        elif name in self.cancellableMoves:
                            oldState = self.state
                            self.resetState()
                            if self.state in attackInput.usableStates:
                                self.cancellableMoves = []
                                return name, False
                            else:
                                self.state = oldState
        return None, False
    def checkAttackInput(self, motion, bufferLength=4):
        leniency = 0
        inputPart = 0
        frameCounter = 0
        #leniencyLogging = []
        backwardsBuffer = list(reversed(self.inputBuffer))
        while frameCounter < len(backwardsBuffer) and inputPart < len(motion):
            if all([any([buttonName in backwardsBuffer[frameCounter] for buttonName in required]) for required in motion[inputPart].buttonList]):
                leniency = bufferLength
                inputPart += 1
                frameCounter += 1
                
            else:
                # first, if this one is optional, check the next one. does it match?
                if motion[inputPart].optional and inputPart+1 < len(motion) and all([any([buttonName in backwardsBuffer[frameCounter] for buttonName in required]) for required in motion[inputPart+1].buttonList]):
                    inputPart += 2
                    frameCounter += 1
                    leniency = 3
                else:
                    leniency -= 1
                    frameCounter += 1
                if leniency < 0:
                    return False
        return inputPart >= len(motion)
            
            
    def Update(self, inputs, inputSystem, enemy, allyProjectiles, enemyProjectiles, boxViewScreen=None, inject=None):
        """
        Updates character's state.
        """
        if self.superFlash > 0:
            pg.draw.rect(boxViewScreen, (0,0,0,0), rect_worldToScreen(boxViewScreen,pg.Rect(0, 0, 456, 50)))
            pg.draw.rect(boxViewScreen, (0,0,0,0), rect_worldToScreen(boxViewScreen,pg.Rect(0, 206, 456, 50)))
        self.superFlash -= 1
        if inject is None:
            inputs = inputSystem.process(inputs, self.inverted)
        else:
            inputs = inject
        self.hitboxes = []
        self.wasHitThisFrame = False
        self.blockedThisFrame = False
        if inputs[0] not in [1, 2, 3] or self.state not in ["grounded_idle", "block"] or self.posy < 200:
            self.hurtboxes = [self.characterData.defaultHurtboxes["standing"]]
        else:
            self.hurtboxes = [self.characterData.defaultHurtboxes["crouching"]]
        if self.hitStop < 1:
            if self.state == "grounded_idle":
                self.velx = 0
                self.doubleJump = self.characterData.midairJumps
                self.resetState()
            if self.state == "jumping":
                if self.stateTime > 0:
                    self.vely = min(self.characterData.jumpMin, self.vely+self.characterData.jumpDecel)
                else:
                    self.resetState()
            elif self.state == "jumpsquat":
                if self.installName == "Mask" and enemy.state in ["hit", "hit_inescapable"]:
                    self.state = "air_idle"
                    self.stateTime = 0
                    self.posx = enemy.posx-40*(-1 if self.inverted else 1)+enemy.velx*5
                    self.posy = enemy.posy+enemy.vely*5
                    self.velx = enemy.velx*1.2
                    self.vely = enemy.vely*1.2
                elif self.stateTime > 0:
                    self.vely = min(self.characterData.jumpMin, self.vely+self.characterData.jumpDecel)
                else:
                    self.state = "jumping"
                    self.stateTime = self.characterData.jumpTime
            elif self.state == "air_idle" or self.state == "special_fall":
                self.velx *= 0.9
                self.vely = min(self.characterData.terminalFall, self.vely+self.characterData.fallAccel)
                self.resetState()
            elif self.state == "attack":
                if self.stateTime > 0:
                    # check and apply hitboxes/hurtboxes for the attack
                    moveTime = self.characterData.attackDict[self.currentAttack].actionableAt - self.stateTime
                    auxiliaryAttack, self.hitboxes, self.hurtboxes, currentProjectile, installData, chargeData, auxiliaryData, selfHealth, selfMeter = self.characterData.attackDict[self.currentAttack].getActiveList(self.characterData.defaultHurtboxes, moveTime)
                    # check perspective
                    attackSuccess = False
                    if auxiliaryAttack and self.auxiliaryActive:
                        attackSuccess = True
                        posx = self.auxiliaryPosX
                        posy = self.auxiliaryPosY
                        inverted = self.auxiliaryInverted
                        # translate hitboxes into proper perspective
                        self.hitboxes = [hitbox.translate(posx-self.posx,posy-self.posy) for hitbox in self.hitboxes]
                        self.hurtboxes = [hurtbox.translate(posx-self.posx,posy-self.posy) for hurtbox in self.hurtboxes]
                        # invert hit/hurtboxes if facing other way
                        if inverted:
                            self.hitboxes = [x.horizontalReflection(posx-self.posx) for x in self.hitboxes]
                            self.hurtboxes = [x.horizontalReflection(posx-self.posx) for x in self.hitboxes]
                    if not(auxiliaryAttack):
                        attackSuccess = True
                        posx = self.posx
                        posy = self.posy
                        inverted = self.inverted
                        # invert hit/hurtboxes if facing other way
                        if inverted:
                            self.hitboxes = [x.horizontalReflection(0) for x in self.hitboxes]
                            self.hurtboxes = [x.horizontalReflection(0) for x in self.hurtboxes]

                    if attackSuccess:
                        # if projectile, then summon said projectile
                        if currentProjectile:
                            allyProjectiles.append(self.characterData.projectileDict[currentProjectile["name"]].createProjectile(inverted,clamp(posx+currentProjectile["pos"]["x"]*(-1 if inverted else 1),0,456),clamp(posy+currentProjectile["pos"]["y"],-9999,200)))
                            #print(allyProjectiles)
                        # if install, then set active install for said time
                        if installData:
                            self.installName = installData["name"]
                            self.installTime = installData["time"]
                        if auxiliaryData:
                            if auxiliaryData["command"] == "remove":
                                self.auxiliaryActive = False
                                self.auxiliaryTime = self.characterData.auxiliaryAutoSummonTime
                                self.auxiliaryCurentAttack = ""
                                self.auxiliaryAttackTime = 0
                            elif auxiliaryData["command"] == "summon":
                                summonX, summonY = 0, 0
                                if "reference" in auxiliaryData:
                                    if auxiliaryData["reference"] == "self":
                                        summonX, summonY = self.posx, self.posy
                                    elif auxiliaryData["reference"] == "enemy":
                                        summonX, summonY = enemy.posx, enemy.posy
                                if "position" in auxiliaryData:
                                    summonX += auxiliaryData["position"]["x"] * (-1 if inverted else 1)
                                    summonY += auxiliaryData["position"]["y"]
                                self.auxiliaryActive = True
                                self.auxiliaryPosX = clamp(summonX, 0, 456)
                                self.auxiliaryPosY = clamp(summonY, -9999, 200)
                        self.chargeLevel = clamp(self.chargeLevel+chargeData, 0, 5)
                        if self.health > 0:
                            self.health = clamp(self.health+selfHealth, 1, self.characterData.maxHealth)
                        self.superMeter = clamp(self.superMeter+selfMeter, 0, 10000)
                    else:
                        self.hitboxes = []
                    # check and apply velocity for the attack
                    if self.hitThisFrame:
                        self.posx += self.velx
                        self.posy += self.vely
                    self.hitThisFrame = False
                    if not(self.characterData.attackDict[self.currentAttack].moving):
                        self.velx, self.vely = 0, 0
                    else:
                        if self.posy < 200:
                            self.vely = min(self.characterData.terminalFall, self.vely+self.characterData.fallAccel)
                        elif self.posy > 200:
                            self.posy = 200
                    if self.characterData.attackDict[self.currentAttack].getVelocity(self.inverted, moveTime)[0] is not None:
                        self.velx, self.vely = self.characterData.attackDict[self.currentAttack].getVelocity(self.inverted, moveTime)
                else:
                    self.resetState()
                    self.jumpCancel = False
                    self.cancellableMoves = []
                    if self.characterData.attackDict[self.currentAttack].specialFall:
                        self.state = "special_fall"
                    self.currentAttack = ""
            elif self.state == "block":
                if self.stateTime > 0:
                    if self.posy < 200:
                        self.vely = min(self.characterData.terminalFall, self.vely+self.characterData.fallAccel)
                    elif self.posy > 200:
                        self.posy = 200
                else:
                    self.resetState()
            elif self.state in ["hit", "hit_inescapable"]:
                # remove auxiliary until over
                self.auxiliaryActive = False
                self.auxiliaryTime = (self.characterData.auxiliaryAutoSummonTime if self.characterData.auxiliaryAutoSummonTime else 0)
                if self.stateTime > 0:
                    if self.posy > 200:
                        self.posy = 200
                    elif self.posy == 200:
                        self.velx = 0
                        self.vely = 0
                else:
                    self.comboedCounter = 0
                    self.comboDamage = 0
                    self.consecutiveBounces = 0
                    self.resetState()
                    if self.nextKnockdown and self.posy > 180:
                        self.posy = 200
                        self.state = self.nextKnockdown
                        self.stateTime = (30 if self.state == "hardKnockdown" else 15)
                        self.nextKnockdown = None
            elif self.state == "softKnockdown":
                self.velx = 0
                self.vely = 0
                if self.stateTime > 0:
                    pass
                else:
                    # allow tech roll in either direction
                    if inputs[0] in [3, 6]:
                        self.posx += 48 * (-1 if self.inverted else 1)
                    elif inputs[0] in [1, 4]:
                        self.posx += 48 * (1 if self.inverted else -1)
                    self.resetState()
            elif self.state == "hardKnockdown":
                self.velx = 0
                self.vely = 0
                if self.stateTime > 0:
                    pass
                else:
                    # no tech roll for you!
                    self.resetState()
            # auxiliary actions
            if self.auxiliaryCurrentAttack and self.auxiliaryActive:
                if self.auxiliaryAttackTime < 1:
                    # end attack
                    self.auxiliaryCurrentAttack = ""
                else:
                    # check and apply hitboxes/hurtboxes for the attack
                    moveTime = self.characterData.attackDict[self.auxiliaryCurrentAttack].actionableAt - self.auxiliaryAttackTime
                    auxiliaryAttack, tempHitboxes, tempHurtboxes, currentProjectile, installData, chargeData, auxiliaryData, selfHealth, selfMeter = self.characterData.attackDict[self.auxiliaryCurrentAttack].getActiveList(self.characterData.defaultHurtboxes, moveTime)
                    # mark that attacks were being used by auxiliary
                    for hitbox in tempHitboxes:
                        hitbox.auxiliary = True
                    # check perspective
                    attackSuccess = False
                    if auxiliaryAttack and self.auxiliaryActive:
                        attackSuccess = True
                        posx = self.auxiliaryPosX
                        posy = self.auxiliaryPosY
                        inverted = self.auxiliaryInverted
                        # translate hitboxes into proper perspective
                        tempHitboxes = [hitbox.translate(posx-self.posx,posy-self.posy) for hitbox in tempHitboxes]
                        tempHurtboxes = [hurtbox.translate(posx-self.posx,posy-self.posy) for hurtbox in tempHurtboxes]
                        # invert hit/hurtboxes if facing other way
                        if inverted:
                            tempHitboxes = [x.horizontalReflection(posx-self.posx) for x in tempHitboxes]
                            tempHurtboxes = [x.horizontalReflection(posx-self.posx) for x in tempHurtboxes]
                    if not(auxiliaryAttack):
                        attackSuccess = True
                        posx = self.posx
                        posy = self.posy
                        inverted = self.inverted
                        # invert hit/hurtboxes if facing other way
                        if inverted:
                            tempHitboxes = [x.horizontalReflection(0) for x in tempHitboxes]
                            tempHurtboxes = [x.horizontalReflection(0) for x in tempHurtboxes]
    
                    if attackSuccess:
                        # if projectile, then summon said projectile
                        if currentProjectile:
                            allyProjectiles.append(self.characterData.projectileDict[currentProjectile["name"]].createProjectile(inverted,clamp(posx+currentProjectile["pos"]["x"]*(-1 if inverted else 1),0,456),clamp(posy+currentProjectile["pos"]["y"],-9999,200)))
                            #print(allyProjectiles)
                        # if install, then set active install for said time
                        if installData:
                            self.installName = installData["name"]
                            self.installTime = installData["time"]
                        if auxiliaryData:
                            if auxiliaryData["command"] == "remove":
                                self.auxiliaryActive = False
                                self.auxiliaryTime = self.characterData.auxiliaryAutoSummonTime
                                self.auxiliaryCurentAttack = ""
                                self.auxiliaryAttackTime = 0
                            elif auxiliaryData["command"] == "summon":
                                summonX, summonY = 0, 0
                                if "reference" in auxiliaryData:
                                    if auxiliaryData["reference"] == "self":
                                        summonX, summonY = self.posx, self.posy
                                    elif auxiliaryData["reference"] == "enemy":
                                        summonX, summonY = enemy.posx, enemy.posy
                                if "position" in auxiliaryData:
                                    summonX += auxiliaryData["position"]["x"] * (-1 if inverted else 1)
                                    summonY += auxiliaryData["position"]["y"]
                                self.auxiliaryActive = True
                                self.auxiliaryPosX = clamp(summonX, 0, 456)
                                self.auxiliaryPosY = clamp(summonY, -9999, 200)
                        self.chargeLevel = clamp(self.chargeLevel+chargeData, 0, 5)
                        if self.health > 0:
                            self.health = clamp(self.health+selfHealth, 1, self.characterData.maxHealth)
                        self.superMeter = clamp(self.superMeter+selfMeter, 0, 10000)
                    else:
                        tempHitboxes = []
                        tempHurtboxes = []
                    self.hitboxes += tempHitboxes
                    self.hurtboxes += tempHurtboxes
                        
            # auxiliary hurtboxes
            if self.auxiliaryActive and "default" in self.characterData.auxiliaryHurtboxes:
                self.hurtboxes.append(self.characterData.auxiliaryHurtboxes["default"].translate(self.auxiliaryPosX-self.posx,self.auxiliaryPosY-self.posy))
            
            
        # PLAYER INPUT WILL GO HERE
        # add to input buffer
        self.inputBuffer.append([str(inputs[0])] + inputs[1])
        self.inputBuffer.popleft()
        # only count initial presses
        prevBtns = []
        for i in range(len(self.inputBuffer)):
            # check held buttons
            btnCheck = [(x[:-5] if "_held" in x else x)for x in prevBtns]
            for j in range(len(self.inputBuffer[i])):
                if self.inputBuffer[i][j] in btnCheck and "_held" not in self.inputBuffer[i][j]:
                    self.inputBuffer[i][j] = self.inputBuffer[i][j] + "_held"
            # check for negative edge
            if i > 0:
                btnCheck = [(x[:-5] if "_held" in x else x)for x in self.inputBuffer[i-1]]
                otherCheck = [(x[:-5] if "_held" in x else x)for x in self.inputBuffer[i]]
                for j in range(len(btnCheck)):
                    if btnCheck[j] not in otherCheck and "_released" not in btnCheck[j] and btnCheck[j] != "5":
                        self.inputBuffer[i].append(btnCheck[j]+"_released")
            prevBtns = self.inputBuffer[i]
        #print(self.inputBuffer[-1])
        # input checks
        if self.hitStop < 1:
            inp, auxiliary = self.checkInput(bufferLength=4)
            if inp:
                # attack has been selected, perform attack
                #print(inp)
                if auxiliary:
                    atk = self.characterData.attackDict[inp]
                    self.auxiliaryAttackTime = atk.actionableAt
                    self.auxiliaryCurrentAttack = inp
                    self.superMeter = min(self.maxMeter, self.superMeter+atk.whiffGain-atk.meterCost)
                else:
                    atk = self.characterData.attackDict[inp]
                    self.state = "attack"
                    self.jumpCancel = False
                    self.cancellableMoves = []
                    self.stateTime = atk.actionableAt
                    self.currentAttack = inp
                    self.hitboxes = []
                    self.superMeter = min(self.maxMeter, self.superMeter+atk.whiffGain-atk.meterCost)
                    self.currentMoveID += 1
                # check for super flash
                if atk.freezing:
                    # draw super flash
                    self.superFlash = 15
                    self.hitStop = 15
                    enemy.hitStop = 15
            
            # movement
            if self.state == "grounded_idle":
                if inputs[0] == 6:
                    self.superMeter = min(self.maxMeter, self.superMeter+12)
                    if self.inverted:
                        self.velx = self.characterData.walkSpeed * -1
                    else:
                        self.velx = self.characterData.walkSpeed
                elif inputs[0] == 4:
                    if self.inverted:
                        self.velx = self.characterData.walkSpeed
                    else:
                        self.velx = self.characterData.walkSpeed * -1

            # auxiliary movement
            if self.characterData.auxiliaryName == "Puppet" and self.auxiliaryActive and self.state not in ["hit","hit_inescapable","block"] and not(self.auxiliaryCurrentAttack):
                if (inputs[0] in [1, 4] if not(self.inverted) else inputs[0] in [3, 6]):
                    self.auxiliaryPosX = clamp(self.auxiliaryPosX-self.characterData.walkSpeed, 0, 456)
                elif (inputs[0] in [3, 6] if not(self.inverted) else inputs[0] in [1, 4]):
                    self.auxiliaryPosX = clamp(self.auxiliaryPosX+self.characterData.walkSpeed, 0, 456)
            
            # jumping
            jumpable = False
            if self.state == "grounded_idle":
                jumpable = True
            elif self.posy < 200 and self.doubleJump:
                if self.state in ["air_idle","jumping","block"]:
                    jumpable = True
                if self.state == "attack" and self.jumpCancel:
                    jumpable = True
            if self.state == "attack" and self.jumpCancel and self.posy == 200:
                jumpable = True
            
            if jumpable:
                if ("7" in self.inputBuffer[-1] or "8" in self.inputBuffer[-1] or "9" in self.inputBuffer[-1] or ("7_held" in self.inputBuffer[-1] or "8_held" in self.inputBuffer[-1] or "9_held" in self.inputBuffer[-1]) and self.posy == 200):
                    if self.jumpReleased:
                        #print("jumpReleased False")
                        self.jumpReleased = False
                        if self.posy < 200:
                            self.doubleJump -= 1
                        if self.state == "attack":
                            self.jumpCancel = False
                        self.state = "jumpsquat"
                        self.stateTime = 4
                        self.vely = -self.characterData.jumpVelocity
                        if "7" in self.inputBuffer[-1] or "7_held" in self.inputBuffer[-1]:
                            # backwards jump
                            if self.inverted:
                                self.velx = self.characterData.walkSpeed
                            else:
                                self.velx = self.characterData.walkSpeed * -1
                        elif "9" in self.inputBuffer[-1] or "9_held" in self.inputBuffer[-1]:
                            # forwards jump
                            self.superMeter = min(self.maxMeter, self.superMeter+125)
                            if self.inverted:
                                self.velx = self.characterData.walkSpeed * -1
                            else:
                                self.velx = self.characterData.walkSpeed
                        else:
                            self.velx = 0
                            self.superMeter = min(self.maxMeter, self.superMeter+125)
                else:
                    if not("7_held" in self.inputBuffer[-1] or "8_held" in self.inputBuffer[-1] or "9_held" in self.inputBuffer[-1]):
                        #print("jumpReleased True")
                        self.jumpReleased = True
            
            
            self.stateTime -= 1
            self.auxiliaryAttackTime -= 1
            autocancelled = False
            # check for ally projectile passive boxes
            for proj in allyProjectiles:
                for allyPassive in proj.data.passiveBoxList:
                    collision = False
                    for hurtbox in self.hurtboxes:
                        if hurtbox.connectedCollide(allyPassive, self.posx, self.posy, proj.posx, proj.posy):
                            collision = True
                    if collision and proj.lifetime > 0:
                        if allyPassive.allyInstall:
                            self.installName = allyPassive.allyInstall["name"]
                            self.installTime = allyPassive.allyInstall["time"]
                            #print(self.installTime)
            # check for enemy projectiles
            for proj in enemyProjectiles:
                for enemyhitbox in proj.hitboxes:
                    collision = False
                    for hurtbox in self.hurtboxes:
                        if hurtbox.connectedCollide(enemyhitbox, self.posx, self.posy, proj.posx, proj.posy) and not(self.state in ["hit", "block"] and enemyhitbox.uncomboable) and not(self.posy < 200 and enemyhitbox.grounded == "only") and not(self.posy >= 200 and enemyhitbox.grounded == "not"):
                            collision = True
                    if collision and self.state not in ["softKnockdown", "hardKnockdown"]:
                        proj.timeTillHit = proj.hitCooldown
                        proj.remainingHits -= 1
    
                        # check hit or blocked and apply state and stun
                        if (((enemyhitbox.blockType == "mid" and inputs[0] in [4, 1, 7])\
                            or (enemyhitbox.blockType == "overhead" and inputs[0] in [4, 7])\
                            or (enemyhitbox.blockType == "low" and inputs[0] == 1))\
                           and self.state in ["grounded_idle","block"]) or (self.state in ["air_idle", "jumping","block"] and self.posy < 200 and inputs[0] in [4, 1, 7]):
                            blocked = True
                        else:
                            blocked = False
                        if blocked:
                            self.state = "block"
                            self.stateTime = enemyhitbox.blockstun
                            self.velx = enemyhitbox.enemyBlockX * (1 if self.inverted else -1)
                            self.vely = enemyhitbox.enemyBlockY
                            # apply chip damage
                            self.health -= enemyhitbox.damage * 0.2
                        else:
                            self.state = ("hit_inescapable" if enemyhitbox.inescapable else "hit")
                            self.stateTime = enemyhitbox.hitstun
                            # apply knockdown
                            self.nextKnockdown = enemyhitbox.knockdownType
                            # apply damage (not scaled yet)
                            self.health -= enemyhitbox.damage
                            self.superMeter = min(self.maxMeter, self.superMeter + enemyhitbox.damage * 2)
                            self.comboDamage += enemyhitbox.damage
                            self.velx = enemyhitbox.enemyHitX * (1 if self.inverted else -1)
                            self.vely = enemyhitbox.enemyHitY
                            self.comboedCounter += 1
                            #print(self.comboedCounter, self.comboDamage)
                            #print(self.velx, self.vely)
                            
    
            
            # check for enemy hurtboxes/damage
            for enemyhitbox in enemy.hitboxes:
                collision = False
                for hurtbox in self.hurtboxes:
                    if hurtbox.connectedCollide(enemyhitbox, self.posx, self.posy, enemy.posx, enemy.posy) and not(self.state in ["hit", "block"] and enemyhitbox.uncomboable) and not(self.posy < 200 and enemyhitbox.grounded == "only") and not(self.posy >= 200 and enemyhitbox.grounded == "not"):
                        collision = True
                if collision and self.state not in ["softKnockdown", "hardKnockdown"] and not(self.hitByID == enemy.currentMoveID and enemyhitbox.hitnum in self.hitByIndexes):
                    enemy.hitThisFrame = True
                    # damage modifiers
                    # bennett field
                    if enemy.installName == "bennettBuff":
                        damage = 1.5 * enemyhitbox.damage
                    else:
                        damage = enemyhitbox.damage
                    # childe charge level
                    if enemy.characterData.name == "Childe":
                        damage = enemyhitbox.damage * (0.7 + (0.15 + (0.05 if enemy.installName == "Foul Legacy" else 0))*enemy.chargeLevel)
                    # check hit or blocked and apply state and stun
                    if (((enemyhitbox.blockType == "mid" and inputs[0] in [4, 1, 7])\
                        or (enemyhitbox.blockType == "overhead" and inputs[0] in [4, 7])\
                        or (enemyhitbox.blockType == "low" and inputs[0] == 1))\
                       and self.state in ["grounded_idle","block"]) or (self.state in ["air_idle", "jumping","block"] and self.posy < 200 and inputs[0] in [4, 1, 7]):
                        blocked = True
                    else:
                        blocked = False
                    if blocked:
                        self.state = "block"
                        self.blockedThisFrame = True
                        self.stateTime = enemyhitbox.blockstun
                        self.velx = enemyhitbox.enemyBlockX
                        self.vely = enemyhitbox.enemyBlockY
                        enemy.velx = enemyhitbox.playerBlockX
                        enemy.vely = enemyhitbox.playerBlockY
                        # apply half hitstop to both
                        self.hitStop = (damage**0.75)//20
                        enemy.hitStop = (damage**0.75)//20
                        # apply chip damage
                        self.health -= damage * 0.2
                        if not(enemyhitbox.auxiliary):
                        # update moves that enemy can cancel into
                            for group in enemy.characterData.inputDict[enemy.currentAttack].cancelOnBlock:
                                enemy.cancellableMoves += enemy.characterData.attackGroups[group]
                            #print(enemy.cancellableMoves)
                    else:
                        self.state = ("hit_inescapable" if enemyhitbox.inescapable else "hit")
                        self.wasHitThisFrame = True
                        self.stateTime = enemyhitbox.hitstun
                        # apply knockdown
                        self.nextKnockdown = enemyhitbox.knockdownType
                        # apply damage
                        self.health -= damage
                        # apply hitstop to both
                        self.hitStop = (damage**0.75)//10
                        enemy.hitStop = (damage**0.75)//10
                        self.superMeter = min(self.maxMeter, self.superMeter + enemyhitbox.damage * 2)
                        self.comboDamage += damage
                        self.velx = enemyhitbox.enemyHitX
                        self.vely = enemyhitbox.enemyHitY
                        enemy.velx = enemyhitbox.playerHitX
                        enemy.vely = enemyhitbox.playerHitY
                        
                        self.comboedCounter += 1
                        #print(self.comboedCounter, self.comboDamage)
                        #print(self.velx, self.vely)

                        # remove own projectiles when hit (leaving one frame left to avoid port priority)
                        for projectile in allyProjectiles:
                            projectile.lifetime = min(projectile.lifetime, 1)

                        if not(enemyhitbox.auxiliary):
                            enemy.superMeter = min(enemy.maxMeter, enemy.superMeter + enemy.characterData.attackDict[enemy.currentAttack].hitGain)
                            # update moves that enemy can cancel into (can only jump cancel on hit)
                            if enemy.characterData.inputDict[enemy.currentAttack].jumpCancellable:
                                enemy.jumpCancel = True
                            for group in enemy.characterData.inputDict[enemy.currentAttack].cancelOnHit:
                                enemy.cancellableMoves += enemy.characterData.attackGroups[group]
                            # if autocancel, then cancel into the specified move
                            if enemy.characterData.inputDict[enemy.currentAttack].autoCancel:
                                inp = enemy.characterData.inputDict[enemy.currentAttack].autoCancel
                                atk = enemy.characterData.attackDict[inp]
                                enemy.state = "attack"
                                enemy.jumpCancel = False
                                enemy.cancellableMoves = []
                                enemy.stateTime = atk.actionableAt
                                enemy.currentAttack = inp
                                enemy.superMeter = min(enemy.maxMeter, enemy.superMeter+atk.whiffGain-atk.meterCost)
                                autocancelled = True
                        else:
                            enemy.superMeter = min(enemy.maxMeter, enemy.superMeter + enemy.characterData.attackDict[enemy.auxiliaryCurrentAttack].hitGain)
                            # if autocancel, then cancel into the specified move
                            if enemy.characterData.inputDict[enemy.auxiliaryCurrentAttack].autoCancel:
                                inp = enemy.characterData.inputDict[enemy.auxiliaryCurrentAttack].autoCancel
                                atk = enemy.characterData.attackDict[inp]
                                enemy.auxiliaryAttackTime = atk.actionableAt
                                enemy.auxiliaryCurrentAttack = inp
                                enemy.superMeter = min(enemy.maxMeter, enemy.superMeter+atk.whiffGain-atk.meterCost)
                                autocancelled = True
                            
                    # make immune to the same hit on the coming frames
                    if self.hitByID == enemy.currentMoveID:
                        self.hitByIndexes.append(enemyhitbox.hitnum)
                    else:
                        self.hitByID = enemy.currentMoveID
                        self.hitByIndexes = [enemyhitbox.hitnum]
    
                    

                    # only update after checking for duplicate hits
                    if autocancelled:
                        enemy.currentMoveID += 1
                    
            self.posx += self.velx
            self.posy += self.vely
    
            # deal with enemy collision
            while self.posx >= enemy.posx and self.posx-enemy.posx < 40 and self.posy == enemy.posy == 200:
                self.posx += 1
            while self.posx < enemy.posx and enemy.posx-self.posx < 40 and self.posy == enemy.posy == 200:
                self.posx -= 1
            
            # clamp positions, causing ground bounce / wallbounce if in hitstun and in air
            if self.state in ["hit"] and self.posy < 200:
                if self.posx < 20:
                    self.posx = 20
                    self.velx *= -0.9
                    self.stateTime += 8 - (16 if self.consecutiveBounces > 1 else 0)
                    self.consecutiveBounces += 1
                elif self.posx + 20 > 455:
                    self.posx = 435
                    self.velx *= -0.9
                    self.stateTime += 16 - (16 if self.consecutiveBounces > 1 else 0)
                    self.consecutiveBounces += 1
            elif self.state in ["hit"] and self.posy > 204:
                self.posy = 202
                self.vely *= -0.9
                self.stateTime += 8 - (8 if self.consecutiveBounces > 1 else 0)
                self.consecutiveBounces += 1
            else:
                if self.posx < 20:
                    self.posx = 20
                elif self.posx + 20 > 455:
                    self.posx = 435
                elif self.posy > 200:
                    self.posy = 200
    
            # invert controls and character
            if self.posy >= 200 and self.state != "attack":
                if self.posx > enemy.posx:
                    self.inverted = True
                elif self.posx < enemy.posx:
                    # make sure not to make corner crossups unblockable
                    self.inverted = False
            if self.state != "attack" and self.auxiliaryActive:
                if self.auxiliaryPosX > enemy.posx:
                    self.auxiliaryInverted = True
                elif self.auxiliaryPosY > enemy.posy:
                    self.auxiliaryInverted = False

            # resummon auxiliary if autosummons
            if self.characterData.auxiliaryAutoSummonTime is not None and self.auxiliaryTime < 1 and not(self.auxiliaryActive):
                self.auxiliaryActive = True
                self.auxiliaryPosX = self.posx
                self.auxiliaryPosY = 200
            if self.auxiliaryTime:
                self.auxiliaryTime -= 1
            self.installTime -= 1
            if self.installTime < 1:
                self.installName = None
        self.hitStop -= 1
        if self.state == "hit":
            colour = (255,0,255,128)
        elif self.state == "hit_inescapable":
            colour = (255,255,0,128)
        elif self.state == "block":
            colour = (0,0,255,128)
        elif self.state == "softKnockdown":
            colour = (128,0,128,128)
        elif self.state == "hardKnockdown":
            colour = (128,128,0,128)
        else:
            colour = self.defaultColour
        
        if boxViewScreen:
            for hurtbox in self.hurtboxes:
                hurtbox.connectedDebugDraw(colour,boxViewScreen, self.posx, self.posy)
            for hitbox in self.hitboxes:
                hitbox.connectedDebugDraw((255,0,0,128),boxViewScreen, self.posx, self.posy)
            if self.auxiliaryActive:
                drawTransparentBox(boxViewScreen, (100,0,255,128), pg.Rect(self.auxiliaryPosX-8, self.auxiliaryPosY-8, 16, 16))

class Input:
    def __init__(self, rightKey, leftKey, upKey, downKey, attackButtonDict):
        self.rightKey = rightKey
        self.leftKey = leftKey
        self.upKey = upKey
        self.downKey = downKey
        self.attackButtonDict = attackButtonDict
    def process(self, getPressed, inverted):
        forwards = (getPressed[self.rightKey] if not(inverted) else getPressed[self.leftKey])
        backwards = (getPressed[self.leftKey] if not(inverted) else getPressed[self.rightKey])
        up = getPressed[self.upKey]
        down = getPressed[self.downKey]

        horizontal = forwards - backwards
        vertical = up - down

        if vertical == 1:
            if horizontal == 1:
                direction = 9
            elif horizontal == 0:
                direction = 8
            else:
                direction = 7
        elif vertical == 0:
            if horizontal == 1:
                direction = 6
            elif horizontal == 0:
                direction = 5
            else:
                direction = 4
        else:
            if horizontal == 1:
                direction = 3
            elif horizontal == 0:
                direction = 2
            else:
                direction = 1

        return direction, [name for name, input in self.attackButtonDict.items() if getPressed[input]]

class MotionInputPart:
    def __init__(self, buttonList, optional):
        self.buttonList = buttonList
        self.optional = optional


class InputData:
    def __init__(self, usableStates, requiredInstall, requiredCharge, requiredAuxiliary, auxiliaryAttack, onlyCancel, cancelOnHit, cancelOnBlock, jumpCancellable, motion, priority, autoCancel):
        self.usableStates = usableStates
        self.requiredInstall = requiredInstall
        self.requiredCharge = requiredCharge
        self.requiredAuxiliary = requiredAuxiliary # if true, attack only allowed when auxiliary is active
        self.auxiliaryAttack = auxiliaryAttack # if true, attack is initiated by auxiliary: instead of checking cancel opportunities, checks if puppet is available
        # can only be used through cancelling into
        self.onlyCancel = onlyCancel
        self.cancelOnHit = cancelOnHit
        self.cancelOnBlock = cancelOnBlock
        self.jumpCancellable = jumpCancellable
        self.motion = motion
        self.priority = priority
        self.autoCancel = autoCancel
    

class GameManager:
    def __init__(self, screen, TRAININGMODE=False):
        self.data = DataReader.readAllCharData(["dehya", "raiden", "venti", "xiao", "bennett", "navia", "childe", "zhongli", "ayaka", "wriothesley", "kaveh", "marionette"])
        self.state = "characterSelect"
        self.TRAININGMODE=TRAININGMODE
        self.characterSelector = CharacterSelect(screen, TRAININGMODE)
        self.fightManager = None
    def Update(self, inputs, screen):
        if self.state == "characterSelect":
            charChoices = self.characterSelector.Update(inputs, screen)
            if charChoices:
                if self.TRAININGMODE:
                    self.fightManager = FightManager(self.data, charChoices[0], charChoices[1], 99, True)
                else:
                    self.fightManager = FightManager(self.data, charChoices[0], charChoices[1], 99, False)
                self.fightManager.startGame()
                self.state = "fight"
        elif self.state == "fight":
            result = self.fightManager.Update(inputs, screen)
            if result:
                self.state = "characterSelect"
                self.characterSelector = CharacterSelect(screen, self.TRAININGMODE)
                self.fightManager = None
    def reset_font_size(self, screen):
        self.characterSelector.reset_font_size(screen)

class CharacterSelect:
    def __init__(self, screen, TRAININGMODE=False):
        self.characterGrid = [
            ["bennett", "venti", "xiao", "zhongli"],
            ["ayaka", "raiden", "dehya", "kaveh"],
            ["navia", "wriothesley", "childe", "marionette"]
        ]
        script_dir = os.path.dirname(__file__)
        with open(os.path.join(script_dir, f"characterDescriptions.json"), "r") as f:
            self.characterDescriptions = json.load(f)
        self.p1Pos = [0, 0]
        self.p2Pos = [0, 0]
        self.p1Selected = False
        self.p2Selected = False
        self.pastInputs = ([], [])
        self.bigFont = pg.font.SysFont("dejavusansmono", font_worldToScreen(screen, 12))
        self.smallFont = pg.font.SysFont("dejavusansmono", font_worldToScreen(screen, 10))
        self.tinyFont = pg.font.SysFont("dejavusansmono", font_worldToScreen(screen, 8))
    def reset_font_size(self, screen):
        self.bigFont = pg.font.SysFont("dejavusansmono", font_worldToScreen(screen, 12))
        self.smallFont = pg.font.SysFont("dejavusansmono", font_worldToScreen(screen, 10))
        self.tinyFont = pg.font.SysFont("dejavusansmono", font_worldToScreen(screen, 8))
    def Update(self, inputs, screen):
        # draw
        pg.draw.rect(screen, (110,110,110), rect_worldToScreen(screen, pg.Rect(0, 0, 456, 256)))
        for i in range(3):
            for j in range(4):
                pg.draw.rect(screen, (0,0,0), rect_worldToScreen(screen, pg.Rect(90+j*69, 8+i*76, 56, 72)))
                if j == self.p1Pos[0] and i == self.p1Pos[1]:
                    pg.draw.rect(screen, ((0,150,0) if not(self.p1Selected) else (0,75,0)), rect_worldToScreen(screen, pg.Rect(94+j*69, 12+i*76, 48, 20)))
                if j == self.p2Pos[0] and i == self.p2Pos[1]:
                    pg.draw.rect(screen, ((0,150,150) if not(self.p2Selected) else (0,75,75)), rect_worldToScreen(screen, pg.Rect(94+j*69, 56+i*76, 48, 20)))

        render = self.bigFont.render(self.characterDescriptions[self.characterGrid[self.p1Pos[1]][self.p1Pos[0]]]["name"].title(),True,(255,255,255))
        rect = render.get_rect()
        rect.left = 8
        rect.top = 8
        screen.blit(render, rect_worldToScreen(screen, rect))
        render = self.smallFont.render(self.characterDescriptions[self.characterGrid[self.p1Pos[1]][self.p1Pos[0]]]["title"].title(),True,(255,255,255))
        rect = render.get_rect()
        rect.left = 8
        rect.top = 240
        screen.blit(render, rect_worldToScreen(screen, rect))
        for i, line in enumerate(self.characterDescriptions[self.characterGrid[self.p1Pos[1]][self.p1Pos[0]]]["moves"]):
            render = self.tinyFont.render(line,True,(255,255,255))
            rect = render.get_rect()
            rect.left = 8
            rect.top = 24+i*16
            screen.blit(render, rect_worldToScreen(screen, rect))

        
        render = self.bigFont.render(self.characterDescriptions[self.characterGrid[self.p2Pos[1]][self.p2Pos[0]]]["name"].title(),True,(255,255,255))
        rect = render.get_rect()
        rect.left = 228
        rect.top = 8
        screen.blit(render, rect_worldToScreen(screen, rect))
        render = self.smallFont.render(self.characterDescriptions[self.characterGrid[self.p2Pos[1]][self.p2Pos[0]]]["title"].title(),True,(255,255,255))
        rect = render.get_rect()
        rect.left = 228
        rect.top = 240
        screen.blit(render, rect_worldToScreen(screen, rect))
        for i, line in enumerate(self.characterDescriptions[self.characterGrid[self.p2Pos[1]][self.p2Pos[0]]]["moves"]):
            render = self.tinyFont.render(line,True,(255,255,255))
            rect = render.get_rect()
            rect.left = 228
            rect.top = 24+i*16
            screen.blit(render, rect_worldToScreen(screen, rect))

        screen.blit(render, rect_worldToScreen(screen, rect))
        render = self.tinyFont.render(" 4D/6D: Throw",True,(255,255,255))
        rect = render.get_rect()
        rect.left = 160
        rect.top = 180+16
        screen.blit(render, rect_worldToScreen(screen, rect))
        render = self.tinyFont.render(" (50%)H+D: Burst",True,(255,255,255))
        rect = render.get_rect()
        rect.left = 160
        rect.top = 180+32
        screen.blit(render, rect_worldToScreen(screen, rect))
        render = self.tinyFont.render(" (50%)L+H: Roman Cancel",True,(255,255,255))
        rect = render.get_rect()
        rect.left = 160
        rect.top = 180+48
        screen.blit(render, rect_worldToScreen(screen, rect))
        
        if not(self.p1Selected):
            if inputs[pg.K_d] and not(self.pastInputs[pg.K_d]):
                self.p1Pos[0] = (self.p1Pos[0] + 1) % 4
            if inputs[pg.K_a] and not(self.pastInputs[pg.K_a]):
                self.p1Pos[0] = (self.p1Pos[0] - 1) % 4
            if inputs[pg.K_w] and not(self.pastInputs[pg.K_w]):
                self.p1Pos[1] = (self.p1Pos[1] - 1) % 3
            if inputs[pg.K_s] and not(self.pastInputs[pg.K_s]):
                self.p1Pos[1] = (self.p1Pos[1] + 1) % 3
            if inputs[pg.K_f]:
                self.p1Selected = True
        if not(self.p2Selected):
            if inputs[pg.K_l] and not(self.pastInputs[pg.K_l]):
                self.p2Pos[0] = (self.p2Pos[0] + 1) % 4
            if inputs[pg.K_j] and not(self.pastInputs[pg.K_j]):
                self.p2Pos[0] = (self.p2Pos[0] - 1) % 4
            if inputs[pg.K_i] and not(self.pastInputs[pg.K_i]):
                self.p2Pos[1] = (self.p2Pos[1] - 1) % 3
            if inputs[pg.K_k] and not(self.pastInputs[pg.K_k]):
                self.p2Pos[1] = (self.p2Pos[1] + 1) % 3
            if inputs[pg.K_LEFTBRACKET]:
                self.p2Selected = True

        if self.p1Selected and inputs[pg.K_g]:
            self.p1Selected = False
        if self.p2Selected and inputs[pg.K_RIGHTBRACKET]:
            self.p2Selected = False

        if self.p1Selected and self.p2Selected:
            return self.characterGrid[self.p1Pos[1]][self.p1Pos[0]], self.characterGrid[self.p2Pos[1]][self.p2Pos[0]]
        
        self.pastInputs = inputs
        return None

class FightManager:
    def __init__(self, characterData, player1Char, player2Char, roundLength, TRAININGMODE):
        self.characterData = characterData
        self.player1Char = player1Char
        self.player2Char = player2Char
        self.roundLength = roundLength
        self.TRAININGMODE=TRAININGMODE
        self.comboTrialManager = TrialManager(DataReader.readComboTrials("comboTrials"), self.characterData)
    def startGame(self):
        self.player1Score = 0
        self.player2Score = 0
        self.roundNumber = 0
        self.scoreIndicator1 = userInterface.ScoreIndicator(144, 52, False)
        self.scoreIndicator2 = userInterface.ScoreIndicator(312, 52, True)
        self.startRound()
    def startRound(self):
        self.roundNumber += 1
        self.state = "roundstart"
        self.roundEnded = False
        self.stateTime = 60
        self.player1 = Character(self.characterData[self.player1Char],180,200,self.characterData[self.player1Char].maxHealth)
        self.player2 = Character(self.characterData[self.player2Char],276,200,self.characterData[self.player2Char].maxHealth, defaultColour=(0, 255, 255, 128))
        self.player2.inverted=True
        self.c1Projectiles = []
        self.c2Projectiles = []
        self.hoverText = [userInterface.HoverText(f"ROUND {self.roundNumber}", 228, 128, 60, (0,0,0), 56)]
        #self.player1.superMeter = 10000
        self.healthBar1 = userInterface.FilledBar(20, 20, 160, 20, True, (255,0,0), (255,255,0),(0,255,0),1)
        self.healthBar2 = userInterface.FilledBar(276, 20, 160, 20, False, (255,0,0), (255,255,0),(0,255,0),1)

        self.superBar1 = userInterface.FilledBar(20, 220, 160, 20, True, (150,150,150), (0,200,150),(0,255,250),0.5)
        self.superBar2 = userInterface.FilledBar(276, 220, 160, 20, False, (150,150,150), (0,200,150),(0,255,250),0.5)

        self.chargeLevel1 = userInterface.ChargeLevel(32, 248, False)
        self.chargeLevel2 = userInterface.ChargeLevel(424, 248, True)

        self.installTimer1 = userInterface.InstallTimer(80, 244, False, (0,255,255))
        self.installTimer2 = userInterface.InstallTimer(301, 244, True, (0,255,255))
        
        self.comboCount2 = userInterface.ComboCounter(60, 80)
        self.comboCount1 = userInterface.ComboCounter(396, 80)

        self.timer = userInterface.Timer(228, 24)
        
        self.input1 = Input(pg.K_d, pg.K_a, pg.K_w, pg.K_s,
                           {
                               "light":pg.K_f,
                               "heavy":pg.K_g,
                               "dust":pg.K_h,
                           })
        self.input2 = Input(pg.K_l, pg.K_j, pg.K_i, pg.K_k,
           {
               "light":pg.K_LEFTBRACKET,
               "heavy":pg.K_RIGHTBRACKET,
               "dust":pg.K_BACKSLASH,
           })
        # not full input handler necessary: using pygame event keys
        self.trainingModeControls = {
            "reset":pg.K_SPACE,
            "leave":pg.K_ESCAPE,
            "nextTrial":pg.K_RIGHT,
            "prevTrial":pg.K_LEFT,
            "switchTrialPlayer":pg.K_LSHIFT
        }
    def Update(self, inputs, screen):
        if self.state == "roundstart":
            pg.draw.rect(screen, (255,255,255), rect_worldToScreen(screen, pg.Rect(0, 0, 456, 256)))
            pg.draw.rect(screen, (220,220,220), rect_worldToScreen(screen, pg.Rect(0, 200, 456, 56)))
            
            self.healthBar1.draw(self.player1.health, self.characterData[self.player1Char].maxHealth, screen)
            self.healthBar2.draw(self.player2.health, self.characterData[self.player2Char].maxHealth, screen)
            
            self.superBar1.draw(self.player1.superMeter, 10000, screen)
            self.superBar2.draw(self.player2.superMeter, 10000, screen)

            self.scoreIndicator1.draw(self.player1Score, screen)
            self.scoreIndicator2.draw(self.player2Score, screen)

            self.comboCount1.Update(screen, self.player1.comboedCounter)
            self.comboCount2.Update(screen, self.player2.comboedCounter)

            for text in self.hoverText:
                text.draw(screen)
            
            if self.stateTime < 1:
                self.hoverText.append(userInterface.HoverText(f"FIGHT", 228, 128, 60, (0,0,0), 12))
                self.state = "round"
                self.stateTime = self.roundLength * 30
        elif self.state == "round":
            pg.draw.rect(screen, (255,255,255), rect_worldToScreen(screen, pg.Rect(0, 0, 456, 256)))
            pg.draw.rect(screen, (220,220,220), rect_worldToScreen(screen, pg.Rect(0, 200, 456, 56)))
            
            p1Control = True
            p2Control = True

            p1Inject = None
            p2Inject = None

            if self.comboTrialManager.trialIndex > 0 and self.comboTrialManager.moveIndex < len(self.comboTrialManager.currentTrial.moves):
                if self.comboTrialManager.currentPlayer == 1:
                    p2Inject = self.comboTrialManager.currentTrial.moves[self.comboTrialManager.moveIndex].enemyInputs
                    p2Control = False
                else:
                    p1Inject = self.comboTrialManager.currentTrial.moves[self.comboTrialManager.moveIndex].enemyInputs
                    p1Control = False

            self.player1.Update(inputs, self.input1, self.player2, self.c1Projectiles, self.c2Projectiles, screen, (None if p1Control else p1Inject))
            self.player2.Update(inputs, self.input2, self.player1, self.c2Projectiles, self.c1Projectiles, screen, (None if p2Control else p2Inject))

            # only update projectiles when game fully moving
            if not(self.player1.superFlash > 0 or self.player2.superFlash > 0 or self.player1.hitStop > 0 or self.player2.hitStop > 0):
                for proj in self.c1Projectiles:
                    proj.Update(screen)
                for proj in self.c2Projectiles:
                    proj.Update(screen)

            self.healthBar1.draw(self.player1.health, self.characterData[self.player1Char].maxHealth, screen)
            self.healthBar2.draw(self.player2.health, self.characterData[self.player2Char].maxHealth, screen)

            self.timer.draw(self.stateTime,screen)
            
            self.superBar1.draw(self.player1.superMeter, 10000, screen)
            self.superBar2.draw(self.player2.superMeter, 10000, screen)

            self.scoreIndicator1.draw(self.player1Score, screen)
            self.scoreIndicator2.draw(self.player2Score, screen)
            
            if self.player1Char == "childe":
                self.chargeLevel1.draw(self.player1.chargeLevel, screen)
            if self.player2Char == "childe":
                self.chargeLevel2.draw(self.player2.chargeLevel, screen)

            if self.player1.installName:
                self.installTimer1.draw(self.player1.installTime, screen)
            if self.player2.installName:
                self.installTimer2.draw(self.player2.installTime, screen)
            
            self.comboCount1.Update(screen, self.player1.comboedCounter)
            self.comboCount2.Update(screen, self.player2.comboedCounter)

            for text in self.hoverText:
                text.draw(screen)
            
            if self.TRAININGMODE:
                # provide way to exit training mode
                if pg.key.get_pressed()[self.trainingModeControls["leave"]]:
                    return 1
                self.trainingMode(screen)
            else:
                if self.player1.health < 1 or self.player2.health < 1 and not(self.roundEnded):
                    self.roundEnded = True
                    self.hoverText.append(userInterface.HoverText("K O", 228, 128, 60, (0,0,0), 120))
                if self.stateTime < 1 and not(self.roundEnded):
                    self.roundEnded = True
                    self.hoverText.append(userInterface.HoverText("TIME UP", 228, 128, 60, (0,0,0), 120))
                if self.roundEnded and self.player1.state not in ["attack", "hit", "hit_inescapable"] and self.player2.state not in ["attack", "hit", "hit_inescapable"] and self.player1.posy > 195 and self.player2.posy > 195:
                    self.state = "roundend"
                    self.stateTime = 60
                    if self.player1.health < 1:
                        self.player2Score += 1
                    elif self.player2.health < 1:
                        self.player1Score += 1
                    elif self.player1.health > self.player2.health:
                        self.player1Score += 1
                    elif self.player2.health > self.player1.health:
                        self.player2Score += 1
        elif self.state == "roundend":
            pg.draw.rect(screen, (255,255,255), rect_worldToScreen(screen, pg.Rect(0, 0, 456, 256)))
            pg.draw.rect(screen, (220,220,220), rect_worldToScreen(screen, pg.Rect(0, 200, 456, 56)))
            
            self.healthBar1.draw(self.player1.health, self.characterData[self.player1Char].maxHealth, screen)
            self.healthBar2.draw(self.player2.health, self.characterData[self.player2Char].maxHealth, screen)

            self.superBar1.draw(self.player1.superMeter, 10000, screen)
            self.superBar2.draw(self.player2.superMeter, 10000, screen)

            self.scoreIndicator1.draw(self.player1Score, screen)
            self.scoreIndicator2.draw(self.player2Score, screen)
            
            self.comboCount1.Update(screen, self.player1.comboedCounter)
            self.comboCount2.Update(screen, self.player2.comboedCounter)
            if self.stateTime < 1 and self.player1Score < 2 and self.player2Score < 2:
                self.startRound()
            elif self.stateTime < 1:
                self.state = "winner"
                self.hoverText = [userInterface.HoverText(f"Player {('1' if self.player1Score > self.player2Score else '2')} Wins", 228, 128, 48, (0,0,0), 120)]
                self.stateTime = 60
        elif self.state == "winner":
            pg.draw.rect(screen, (255,255,255), rect_worldToScreen(screen, pg.Rect(0, 0, 456, 256)))
            for text in self.hoverText:
                text.draw(screen)

            if self.stateTime < 1:
                return (1 if self.player1Score > self.player2Score else 2)
        self.stateTime -= 1
        return 0
    def trainingMode(self, screen):
        # freeze timer
        self.stateTime = self.roundLength * 30

        # reset P1/P2 health when not in hit/blockstun
        # give both players max meter when the other is not in hit/blockstun (while combo continues)
        if self.player1.state not in ["hit", "hit_inescapable", "blockstun", "soft_knockdown", "hard_knockdown"]:
            self.player1.health = self.player1.characterData.maxHealth
            self.player2.superMeter = 10000
        if self.player2.state not in ["hit", "hit_inescapable", "blockstun", "soft_knockdown", "hard_knockdown"]:
            self.player2.health = self.player2.characterData.maxHealth
            self.player1.superMeter = 10000
        
        # if space pressed, reset training mode
        # MAKE SURE NOT TO PUMP INPUTS
        eventQueue=pg.event.get(pg.KEYDOWN, False)
        for event in eventQueue:
            if event.key == self.trainingModeControls["reset"]:
                self.trainingReset()
            if event.key == self.trainingModeControls["nextTrial"]:
                self.comboTrialManager.updateTrial(self, 1)
            if event.key == self.trainingModeControls["prevTrial"]:
                self.comboTrialManager.updateTrial(self, -1)
        self.comboTrialManager.Update(screen, self, self.player1, self.player2)
    def trainingReset(self):
        getPressed=pg.key.get_pressed()
        self.startRound()
        self.hoverText = []
        self.stateTime = 1
        if self.comboTrialManager.trialIndex == 0:
            if getPressed[self.input1.rightKey]:
                self.player2.posx=456
                self.player1.posx=400
            elif getPressed[self.input1.leftKey]:
                self.player2.posx=0
                self.player1.posx=56
            elif getPressed[self.input2.rightKey]:
                self.player2.posx=400
                self.player1.posx=456
            elif getPressed[self.input2.leftKey]:
                self.player2.posx=56
                self.player1.posx=0
            elif getPressed[self.input2.downKey]:
                temp = self.player2.posx
                self.player2.posx = self.player1.posx
                self.player1.posx = temp
        else:
            # reset positions based on current trial specifics
            if self.comboTrialManager.currentPlayer == 1:
                if self.comboTrialManager.currentTrial.startingPosition == "middle":
                    if self.comboTrialManager.inverted:
                        temp = self.player2.posx
                        self.player2.posx = self.player1.posx
                        self.player1.posx = temp
                elif self.comboTrialManager.currentTrial.startingPosition == "cornering":
                    if self.comboTrialManager.inverted:
                        self.player2.posx = 0
                        self.player1.posx = 56
                    else:
                        self.player2.posx=456
                        self.player1.posx=400
                elif self.comboTrialManager.currentTrial.startingPosition == "cornered":
                    if self.comboTrialManager.inverted:
                        self.player2.posx = 400
                        self.player1.posx = 456
                    else:
                        self.player2.posx=56
                        self.player1.posx=0
            elif self.comboTrialManager.currentPlayer == 2:
                if self.comboTrialManager.currentTrial.startingPosition == "middle":
                    if self.comboTrialManager.inverted:
                        temp = self.player1.posx
                        self.player1.posx = self.player1.posx
                        self.player2.posx = temp
                elif self.comboTrialManager.currentTrial.startingPosition == "cornering":
                    if self.comboTrialManager.inverted:
                        self.player1.posx = 0
                        self.player2.posx = 56
                    else:
                        self.player1.posx=456
                        self.player2.posx=400
                elif self.comboTrialManager.currentTrial.startingPosition == "cornered":
                    if self.comboTrialManager.inverted:
                        self.player1.posx = 400
                        self.player2.posx = 456
                    else:
                        self.player1.posx=56
                        self.player2.posx=0

class TrialManager:
    def __init__(self, trials, characterData):
        self.trials = trials
        self.characterData = characterData
        self.currentPlayer = 1
        self.trialIndex = 0 # 0 is default training mode, 1 onwards is character trials
        self.inverted = False
        self.currentTrials = None
        self.currentTrial = None
        self.hitCount = 0
        self.moveIndex = 0 # if move index greater than number of moves in trial, it's completed, display Complete! instead of trial name
    def updateTrial(self, fightManager, amount):
        self.trialIndex = (self.trialIndex + amount)%(len(self.currentTrials))
        self.currentTrial = self.currentTrials[self.trialIndex]
        self.hitCount = 0
        self.moveIndex = 0
        #print(self.currentTrials)
        # reset training mode to proper positioning
        fightManager.trainingReset()

    def Update(self, screen, fightManager, player1, player2):
        x_scale = screen.get_size()[0]/456
        y_scale = screen.get_size()[1]/256
        scale = min(x_scale, y_scale)
        main_font = pg.font.SysFont("dejavusansmono", font_worldToScreen(screen, 12))
        self.player1 = player1
        self.player2 = player2
        self.currentTrials = [None]+self.trials[(self.player1 if self.currentPlayer == 1 else self.player2).characterData.name.lower()]
        if self.trialIndex == 0:
            self.currentTrial = None

            # display "FREE TRAINING"
            render = main_font.render("FREE TRAINING", True, (0,0,0))
            rect = render.get_rect()
            rect.left = 180
            rect.top = 200
            screen.blit(render, rect_worldToScreen(screen, rect))

            return 0
        else:
            self.currentTrial = self.currentTrials[self.trialIndex]

            # display trial name
            render = main_font.render(self.currentTrial.name, True, (0,0,0))
            rect = render.get_rect()
            rect.left = 180
            rect.top = 200
            screen.blit(render, rect_worldToScreen(screen, rect))

            # display how far in trial
            drawTransparentBox(screen, (80,255,0,50), pg.Rect(56,64,150,(min(self.moveIndex,len(self.currentTrial.moves)))*16))

            # display trial parts
            for i in range(len(self.currentTrial.moves)):
                if self.currentTrial.moves[i].hitType == "hit":
                    indicator = ""
                elif self.currentTrial.moves[i].hitType == "block":
                    indicator = "(Blocked)"
                elif self.currentTrial.moves[i].hitType == "miss":
                    indicator = "(Miss)"
                indicator += (f"[{self.currentTrial.moves[i].hitCount}]" if self.currentTrial.moves[i].hitCount != 1 else "")
                curr_name = ("[KD]" if self.currentTrial.moves[i].continueAfterKnockdown else "") + self.currentTrial.moves[i].name + indicator
                render = main_font.render(curr_name, True, (0,0,0))
                rect = render.get_rect()
                rect.left = 56
                rect.top = 64+i*16
                screen.blit(render, rect_worldToScreen(screen, rect))
            
            # check trial progress
            player = (player1 if self.currentPlayer == 1 else player2)
            enemy = (player2 if self.currentPlayer == 1 else player1)

            if self.moveIndex < len(self.currentTrial.moves):
                curr_move = self.currentTrial.moves[self.moveIndex]
                
                if curr_move.hitType == "hit":
                    if enemy.wasHitThisFrame and player.hitThisFrame:
                        print(f"{player.currentAttack}")
                        if player.currentAttack == curr_move.name:
                            self.hitCount += 1
                            if curr_move.hitCount <= self.hitCount:
                                self.moveIndex += 1
                                self.hitCount = 0
                        else:
                            self.moveIndex = 0
                            self.hitCount = 0
                    
                elif curr_move.hitType == "block":
                    if enemy.blockedThisFrame and player.hitThisFrame:
                        if player.currentAttack == curr_move.name:
                            self.hitCount += 1
                            if curr_move.hitCount <= self.hitCount:
                                self.moveIndex += 1
                                self.hitCount = 0
                        else:
                            self.moveIndex = 0
                            self.hitCount = 0
                elif curr_move.hitType == "miss":
                    if player.currentAttack == curr_move.name:
                        self.hitCount += 1
                        if curr_move.hitCount <= self.hitCount:
                            self.moveIndex += 1
                            self.hitCount = 0
            
                if enemy.state not in (["hit","hit_inescapable","block","softKnockdown","hardKnockdown"] if curr_move.continueAfterKnockdown else ["hit","hit_inescapable","block"]):
                    self.moveIndex = 0
                    self.hitCount = 0



class ComboTrial:
    def __init__(self, name, description, startingPosition, moves):
        self.name = name
        self.description = description
        self.startingPosition = startingPosition
        self.moves = moves

class ComboMove:
    def __init__(self, name, hitType, continueAfterKnockdown=False, enemyInputs=[5,[]], hitCount=1):
        self.name = name
        self.hitType = hitType
        self.continueAfterKnockdown = continueAfterKnockdown
        self.enemyInputs = enemyInputs
        self.hitCount = hitCount



class DataReader:
    def __init__(self):
        pass
    @staticmethod
    def readBox(boxDict):
        return Box(boxDict["left"],boxDict["top"],boxDict["length"],boxDict["height"],True)
    @staticmethod
    def readHurtbox(boxDict):
        return Hurtbox(boxDict["left"],boxDict["top"],boxDict["length"],boxDict["height"],True)
    @staticmethod
    def readHitbox(hitboxDict):
        return Hitbox(DataReader.readBox(hitboxDict["box"]),hitboxDict["stats"]["damage"],hitboxDict["stats"]["hitstun"],hitboxDict["stats"]["blockstun"],hitboxDict["stats"]["block"],(hitboxDict["stats"]["inescapable"] if "inescapable" in hitboxDict["stats"] else False),(hitboxDict["stats"]["uncomboable"] if "uncomboable" in hitboxDict["stats"] else False),(hitboxDict["stats"]["grounded"] if "grounded" in hitboxDict["stats"] else False),(hitboxDict["stats"]["knockdown"] if "knockdown" in hitboxDict["stats"] else None),
                     hitboxDict["stats"]["enemyBlockVel"]["velx"],hitboxDict["stats"]["enemyBlockVel"]["vely"],hitboxDict["stats"]["playerBlockVel"]["velx"],hitboxDict["stats"]["playerBlockVel"]["vely"],hitboxDict["stats"]["enemyHitVel"]["velx"],hitboxDict["stats"]["enemyHitVel"]["vely"],hitboxDict["stats"]["playerHitVel"]["velx"],hitboxDict["stats"]["playerHitVel"]["vely"])
    @staticmethod
    def readPassivebox(passiveDict):
        return PassiveBox(DataReader.readBox(passiveDict["box"]),(passiveDict["stats"]["allyInstall"] if "allyInstall" in passiveDict["stats"] else False))
    @staticmethod
    def readFrameData(frameDataDict, largestHitnum):
        hitboxList = []
        for i, hitbox in enumerate(frameDataDict["hitboxes"]):
            hitboxList.append(DataReader.readHitbox(hitbox))
            hitboxList[i].hitnum = largestHitnum+1
        hurtboxList = [DataReader.readHurtbox(x) for x in frameDataDict["hurtboxes"]]
        velxOverride, velyOverride = None, None
        if "velocityOverride" in frameDataDict:
            velxOverride = frameDataDict["velocityOverride"]["velx"]
            velyOverride = frameDataDict["velocityOverride"]["vely"]
        return FrameData((frameDataDict["auxiliary"] if "auxiliary" in frameDataDict else False), frameDataDict["frames"]["min"],frameDataDict["frames"]["max"], hitboxList, hurtboxList, (frameDataDict["projectile"] if "projectile" in frameDataDict else None), (frameDataDict["installData"] if "installData" in frameDataDict else None), (frameDataDict["chargeData"] if "chargeData" in frameDataDict else 0), (frameDataDict["auxiliaryData"] if "auxiliaryData" in frameDataDict else 0), (frameDataDict["selfHealth"] if "selfHealth" in frameDataDict else 0), (frameDataDict["selfMeter"] if "selfMeter" in frameDataDict else 0), frameDataDict["defaultActive"], velxOverride, velyOverride)
    @staticmethod
    def readAttack(attackDict):
        frameDataList = []
        largestHitnum = -1
        for i, x in enumerate(attackDict["frameData"]):
            frameDataList.append(DataReader.readFrameData(x, largestHitnum))
            largestHitnum += 1
        return Attack(attackDict["actionableAt"],(attackDict["specialFall"] if "specialFall" in attackDict else False),(attackDict["moving"] if "moving" in attackDict else False),attackDict["whiffGain"],attackDict["hitGain"],(attackDict["freezing"] if "freezing" in attackDict else False),frameDataList,(attackDict["meterCost"] if "meterCost" in attackDict else 0))
    @staticmethod
    def readProjectile(projDict):
        hitboxList = []
        for i, hitbox in enumerate(projDict["hitboxes"]):
            hitboxList.append(DataReader.readHitbox(hitbox))
            hitboxList[i].hitnum = -1
        hurtboxList = [DataReader.readHurtbox(x) for x in projDict["hurtboxes"]]
        return ProjectileData(projDict["lifetime"],projDict["maxHits"],projDict["hitCooldown"], hitboxList, hurtboxList, ([DataReader.readPassivebox(x) for x in projDict["passiveboxes"]] if "passiveboxes" in projDict else []), projDict["motion"]["velocity"]["x"],projDict["motion"]["velocity"]["y"],projDict["motion"]["acceleration"]["x"],projDict["motion"]["acceleration"]["y"])
    @staticmethod
    def readMotion(motionDict):
        return MotionInputPart(motionDict["btns"],motionDict["optional"])
    @staticmethod
    def readInput(inputSpecs):
        motion = ([DataReader.readMotion(x) for x in inputSpecs["input"]["motion"]] if "input" in inputSpecs else False)
        return InputData(inputSpecs["statesUsableFrom"],(inputSpecs["requiredInstall"] if "requiredInstall" in inputSpecs else None),(inputSpecs["requiredCharge"] if "requiredCharge" in inputSpecs else None),(inputSpecs["requiredAuxiliary"] if "requiredAuxiliary" in inputSpecs else False),(inputSpecs["auxiliary"] if "auxiliary" in inputSpecs else False),(inputSpecs["onlyCancel"] if "onlyCancel" in inputSpecs else False),inputSpecs["cancelStates"]["hit"],inputSpecs["cancelStates"]["block"],inputSpecs["jumpCancellable"],motion,(inputSpecs["input"]["priority"] if "input" in inputSpecs else False),(inputSpecs["autoCancel"] if "autoCancel" in inputSpecs else ""))
    @staticmethod
    def readCharacterData(characterDataDict):
        defaultHurtboxes = {name:DataReader.readHurtbox(data) for name, data in characterDataDict["defaultHurtboxes"].items()}
        if "auxiliary" in characterDataDict:
            auxiliaryHurtboxes = {name:DataReader.readHurtbox(data) for name, data in characterDataDict["auxiliary"]["hurtboxes"].items()}
        else:
            auxiliaryHurtboxes = []
        attackDict = {name:DataReader.readAttack(data) for name, data in characterDataDict["attacks"].items()}
        inputDict = {name:DataReader.readInput(data) for name, data in characterDataDict["inputData"].items()}
        projDict = {name:DataReader.readProjectile(data) for name, data in characterDataDict["projectiles"].items()}
        return CharacterData(characterDataDict["name"],
                             characterDataDict["attributes"]["walkSpeed"],characterDataDict["attributes"]["health"],(characterDataDict["attributes"]["midairJumps"] if "midairJumps" in characterDataDict["attributes"] else 1),
                             characterDataDict["attributes"]["jump"]["initialVelocity"],
                             characterDataDict["attributes"]["jump"]["deceleration"],
                             characterDataDict["attributes"]["jump"]["minSpeed"],
                             characterDataDict["attributes"]["jump"]["totalTime"],
                             characterDataDict["attributes"]["fallAccel"],
                             characterDataDict["attributes"]["terminalFall"],
                             defaultHurtboxes,attackDict,inputDict,projDict,characterDataDict["attackGroups"],
                            (characterDataDict["auxiliary"]["name"] if "auxiliary" in characterDataDict else None),(characterDataDict["auxiliary"]["autoSummonTime"] if "auxiliary" in characterDataDict and "autoSummonTime" in characterDataDict["auxiliary"] else None), auxiliaryHurtboxes)
    @staticmethod
    def readAllCharData(filenames):
        script_dir = os.path.dirname(__file__)
        characterData = dict()
        for filename in filenames:
            with open(os.path.join(script_dir,f"characterData/{filename}.json"), "r") as f:
                #print(filename)
                characterData[filename] = DataReader.readCharacterData(json.load(f))
        return characterData

    @staticmethod
    def readComboMove(comboMoveDict):
        return ComboMove(
            comboMoveDict["name"],
            comboMoveDict["hitType"],
            (False if not "continueAfterKnockdown" in comboMoveDict else comboMoveDict["continueAfterKnockdown"]),
            ([5,[]] if not "enemyInputs" in comboMoveDict else comboMoveDict["enemyInputs"]),
            (1 if not "hitCount" in comboMoveDict else comboMoveDict["hitCount"]),
        )
    @staticmethod
    def readComboTrial(comboTrialDict):
        return ComboTrial(
            comboTrialDict["name"],
            comboTrialDict["description"],
            comboTrialDict["startingPosition"],
            [DataReader.readComboMove(m) for m in comboTrialDict["moves"]]
        )

    @staticmethod
    def readComboTrials(filename):
        script_dir = os.path.dirname(__file__)
        trialsPerChar = dict()
        with open(os.path.join(script_dir,f"{filename}.json"),"r") as f:
            raw = json.load(f)
        for charName, charData in raw.items():
            if charName[0] != "#":
                trialsPerChar[charName] = [DataReader.readComboTrial(c) for c in charData]
        return trialsPerChar