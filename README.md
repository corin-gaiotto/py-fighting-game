# Pygame Fighting Game / Engine

## What is this?
A fighting game engine built from the ground up with Pygame. There is also a sample configuration of this engine, inspired by games such as Guilty Gear.

## Engine features
- Collision detection
- Attack and character data as configurable JSON
- - hurtboxes
- - hitboxes
- - startup
- - active frames
- - recovery
- - motion inputs
- Motion input detection + Lenient input buffer
- - Implemented using a secondary interface connecting actual inputs and game inputs, which controls a deque of input states which cycles every frame
- - Support for custom inputs, including negative edge (button releases)
- Traditional 2D blocking system
- - differentiate between highs, lows, and mids, and allow air blocking all hits, but with vulnerable jump startup
- Universal move cancel system with room for differentiation between hit and block
- - Custom named move groups allow for more variance in move cancels from character to character
- State machine-controlled characters
- - Inputs can be configured to be read differently based on state - for example, moves usable only on the ground, in the air, when taking damage, or more
- Easy to modify input system - add or remove buttons and change keybindings programmatically
- Configurable projectile system, with variable position, velocity, and acceleration
- Combo Counter
- Training mode
- - Reset with different positions (roundstart, left/right corner, swap P1 and P2 position)
- - Configurable JSON combo trials
- - - Includes blockstring functionality, whiffed moves mid-combo, and specific amounts of hits from multi-hit moves
- Runs at stable 30 FPS even on lower-end machines
