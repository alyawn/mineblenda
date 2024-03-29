import bpy
from bpy.props import FloatVectorProperty
###from add_utils import AddObjectHelper, add_object_data
from mathutils import Vector

from . import blockbuild	#import *?

#gonna be using blockbuild.createMCBlock(mcname, diffuseColour, mcfaceindices) (bottom, top, right, front, left, back!)

# Acro's Python3.2 NBT Reader for Blender Importing Minecraft

import sys, os, gzip
import datetime
#from struct import calcsize, unpack, error as StructError

#tag classes: switch/override the read functions once they know what they are
#and interpret payload by making more taggy bits as needed inside self.
#maybe add mcpath as a context var so it can be accessed from operators.

REPORTING = {}
REPORTING['totalchunks'] = 0
totalchunks = 0
wseed = None	#store chosen world's worldseed here for handy referencing for slimechunk determination.

#TODO: loading custom save locations rather than default saves folder. good for backup/server game reading.
# what's a good way to swap out the world-choice dialogue for a custom path input??

MCREGION_VERSION_ID = 0x4abc;	# Check the world's level.dat 'version' property for these.
ANVIL_VERSION_ID = 0x4abd;		# 

MCPATH = ''
MCSAVEPATH = ''
if sys.platform == 'darwin':
    MCPATH = os.path.join(os.environ['HOME'], 'Library', 'Application Support', 'minecraft')
elif sys.platform == 'linux2':
    MCPATH = os.path.join(os.environ['HOME'], '.minecraft')
else:
    MCPATH = os.path.join(os.environ['APPDATA'], '.minecraft')

MCSAVEPATH = os.path.join(MCPATH, 'saves/')
    
#TODO: Retrieve these from bpy.props properties stuck in the scene RNA...
EXCLUDED_BLOCKS = [1, 3]    #(1,3) # hack to reduce loading / slowdown: (1- Stone, 3- Dirt). Other usual suspects are Grass,Water, Leaves, Sand,StaticLava

LOAD_AROUND_3D_CURSOR = False  #calculates 3D cursor as a Minecraft world position, and loads around that instead of player (or SMP world spawn) position

unknownBlockIDs = set()

OPTIONS = {}

#"Profile" execution time checks for measuring whether optimisations are worth it:

REPORTING['blocksread'] = 0
#blocksRead = 0
REPORTING['blocksdropped'] = 0
#blocksDropped = 0
t0 = datetime.datetime.now()
tReadAndBuffered = -1
tToMesh = -1
tChunk0 = -1	#these don't need to be globals - just store the difference in the arrays.
tChunkEnd = -1
tRegion0 = -1
tRegionEnd = -1
tChunkReadTimes = []
tRegionReadTimes = []

WORLD_ROOT = None

#MCBINPATH -- in /bin, zipfile open minecraft.jar, and get terrain.png.
#Feed directly into Blender, or save into the Blender temp dir, then import.
print(MCPATH)

# level.dat and region files and anvil files have different formats, but all are NBT structured.

from . import nbtreader	# import TagReader

#Blockdata is: [name, diffusecolour RGB triple, (textureID_top, textureID_bottom, textureID_sides) triple or None if nonsquare, custommodel etc]
# Texture IDs are the 1d (2d) count of location of their 16x16 square within terrain.png in minecraft.jar

#Don't store a name for air. Ignore air.
# Order for Blender cube face creation is: [bottom, top, right, front, left, back]

BLOCKDATA = {0: ['Air'],
            1: ['Stone', (116,116,116), [1,1,1,1,1,1]],
            2: ['Grass', (95,159,53), [2,0,3,3,3,3]],    #[bot, top, right, front, left, back] - top is 0; grass is biome tinted, though.
            3: ['Dirt', (150, 108, 74), [2,2,2,2,2,2]],
            4: ['Cobblestone', (94,94,94), [16,16,16,16,16,16]],
            5: ['WoodenPlank', (159,132,77), [4,4,4,4,4,4]],
            6: ['Sapling', (0,100,0), [15]*6, 'XD', 'xfull'],
            7: ['Bedrock', [51,51,51], [17]*6],
            8: ['WaterFlo', (31,85,255), [207]*6],
            9: ['Water', (62,190,255), [207]*6],
            10: ['LavaFlo', (252,0,0), [255]*6, None, None, None, {'emit': 1.10, 'transp': False}],
            11: ['Lava',    (230,0,0), [255]*6, None, None, None, {'emit': 1.10, 'transp': False}],
            12: ['Sand', (214,208,152), [18]*6],
            13: ['Gravel', (154,135,135), [19]*6],
            14: ['GoldOre', (252,238,75), [32]*6],
            15: ['IronOre', (216,175,147), [33]*6],
            16: ['CoalOre', (69,69,69), [34]*6],
            17: ['Wood', (76,61,38), [21,21,20,20,20,20], 'XD'],
            18: ['Leaves', (99,128,15), [53]*6],
            19: ['Sponge', (206,206,70), [48]*6],
            20: ['Glass', (254,254,254), [49]*6, None, None, None, {'transp': True}],
            21: ['LapisLazuliOre', (28,87,198), [160]*6],
            22: ['LapisLazuliBlock', (25,90,205), [144]*6],
            23: ['Dispenser', (42,42,42), [62,62,45,46,45,45]],
            24: ['Sandstone', (215,209,153), [208,176,192,192,192,192], 'XD'],
            25: ['NoteBlock', (145,88,64), [74]*6],
            26: ['Bed'],    #inset, directional
            27: ['PwrRail', (204,93,22), [163]*6, 'XD', 'onehigh', None, {'transp': True}],	#meshtype-> "rail". define as 1/16thHeightBlock, read extra data to find orientation.
            28: ['DetRail', (134,101,100), [195]*6, 'XD', 'onehigh', None, {'transp': True}],	#change meshtype to "rail" for purposes of slanted bits. later. PLANAR, too. no bottom face.
            29: ['StickyPiston', (114,120,70), [109,106,108,108,108,108], 'XD', 'pstn'],
            30: ['Cobweb', (237,237,237), [11]*6, 'none', 'xfull', None, {'transp': True}],
            31: ['TallGrass', (52,79,45), [180,180,39,39,39,39], 'XD', 'xhi', None, {'transp': True}],
            32: ['DeadBush', (148,100,40), [55]*6, None, None, None, {'transp': True}],
            33: ['Piston', (114,120,70), [109,107,108,108,108,108], 'XD', 'pstn'],
            34: ['PistonHead', (188,152,98), [180,107,180,180,180,180]],	#or top is 106 if sticky (extra data)
            35: ['Wool', (235,235,235), [64]*6, 'XD'],  #XD means use xtra data...
            37: ['Dandelion', (204,211,2), [13]*6, 'no', 'xfull', None, {'transp': True}],
            38: ['Rose', (247,7,15), [12]*6, 'no', 'xfull', None, {'transp': True}],
            39: ['BrownMushrm', (204,153,120), [29]*6, 'no', 'xfull', None, {'transp': True}],
            40: ['RedMushrm', (226,18,18), [28]*6, 'no', 'xfull', None, {'transp': True}],
            41: ['GoldBlock', (255,241,68), [23]*6],
            42: ['IronBlock', (230,230,230), [22]*6],
            43: ['DblSlabs', (255,255,0), [6,6,5,5,5,5], 'XD', 'twoslab'],	#xd for type
            44: ['Slabs', (255,255,0), [6,6,5,5,5,5], 'XD', 'slab'],	#xd for type
            45: ['BrickBlock', (124,69,24), [7]*6],
            46: ['TNT', (219,68,26), [10,9,8,8,8,8]],
            47: ['Bookshelf', (180,144,90), [4,4,35,35,35,35]],
            48: ['MossStone', (61,138,61), [36]*6],
            49: ['Obsidian', (60,48,86), [37]*6],
            50: ['Torch', (240,150,50), [80,80,80,80,80,80], 'XD', 'inset', [0,6,7]],
            51: ['Fire', (255,100,100), [10]*6, None, 'hash', None, {'emit': 1.0, 'transp': True}],	#TODO: Needed for Nether. use crops mesh '#'
            52: ['MonsterSpawner', (27,84,124), [65]*6, None, None, None, {'transp': True}],	#xtra data for what's spinning inside it??
            53: ['WoodenStairs', (159,132,77), [4,4,4,4,4,4], 'XD', 'stairs'],
            54: ['Chest', (164,114,39), [25,25,26,27,26,26], 'XD', 'chest'],    #texface ordering is wrong
            55: ['RedStnWire', (255,0,3), [165]*6, 'XD', 'onehigh', None, {'transp': True}],	#direction-dependent, needs extra data. Also texture needs to act as bitmask alpha only, onto material colour on this thing. :S
            56: ['DiamondOre', (93,236,245), [50]*6],
            57: ['DiamondBlock', (93,236,245), [24]*6],
            58: ['CraftingTbl', (160,105,60), [43,43,59,60,59,60]],
            59: ['Seeds', (160,184,0), [180,180,94,94,94,94], 'XD', 'crops', None, {'transp': True}],
            60: ['Farmland', (69,41,21), [2,87,2,2,2,2]],
            61: ['Furnace', (42,42,42), [62,62,45,44,45,45]],		#[bottom, top, right, front, left, back]
            62: ['Burnace', (50,42,42), [62,62,45,61,45,45]],
            63: ['SignPost', (159,132,77), [4,4,4,4,4,4], 'XD', 'sign'],
            64: ['WoodDoor', (145,109,56), [97,97,81,81,81,81], 'XD', 'door', None, {'transp': True}],
            65: ['Ladder', (142,115,60), [83]*6, None, None, None, {'transp': True}],
            66: ['Rail', (172,136,82), [180,128,180,180,180,180], 'XD', 'onehigh', None, {'transp': True}],	#to be refined for direction etc.
            67: ['CobbleStairs', (77,77,77), [16]*6, 'XD', 'stairs'],
            68: ['WallSign', (159,132,77), [4,4,4,4,4,4], 'XD', 'wallsign'],	#TODO: UVs etc! Model!
            69: ['Lever', (105,84,51), [96]*6, 'XD', 'lever'],
            70: ['StnPressPlate', (110,110,110), [1]*6, 'no', 'onehigh'],
            71: ['IronDoor', (183,183,183), [98,98,82,82,82,82], 'XD', 'door', None, {'transp': True}],
            72: ['WdnPressPlate', (159,132,77), [4]*6, 'none', 'onehigh'],
            73: ['RedstOre', (151,3,3), [51]*6],
            74: ['RedstOreGlowing', (255,3,3), [51]*6],	#wth!
            75: ['RedstTorchOff', (86,0,0), [115]*6, 'XD', 'inset', [0,6,7]],  #TODO Proper RStorch mesh
            76: ['RedstTorchOn', (253,0,0), [99]*6, 'XD', 'inset', [0,6,7]],  #todo: 'rstorch'
            77: ['StoneButton', (116,116,116), [1]*6, 'btn'],
            78: ['Snow', (240,240,240), [66]*6, 'XD', 'onehigh'],	#snow has height variants 0-7. 7 is full height block. Curses!
            79: ['Ice', (220,220,255), [67]*6],
            80: ['SnowBlock', (240,240,240), [66]*6],
            81: ['Cactus', (20,141,36), [71,69,70,70,70,70], 'none', 'cactus'],
            82: ['ClayBlock', (170,174,190), [72]*6],
            83: ['SugarCane', (130,168,89), [73]*6, None, None, None, {'transp': True}],
            84: ['Jukebox', (145,88,64), [75,74,74,74,74,74]],	#XD
            85: ['Fence', (160,130,70), [4]*6],	#fence mesh, extra data.
            86: ['Pumpkin', (227,144,29), [118,102,118,118,118,118]],
            87: ['Netherrack', (137,15,15), [103]*6],
            88: ['SoulSand', (133,109,94), [104]*6],
            89: ['Glowstone', (114,111,73), [105]*6, None, None, None, {'emit': 0.95, 'transp': False}],	#cycles: emitter!
            90: ['Portal', (150,90,180), None],
            91: ['JackOLantern',(227,144,29), [118,102,118,119,118,118], 'XD'],	#needs its facing dir.
            92: ['Cake', (184,93,39), [124,121,122,122,122,122], 'XD', 'inset', [0,8,1]],
            93: ['RedRepOff', (176,176,176), [131]*6, 'xdcircuit', 'onehigh'],	#TODO 'redrep' meshtype
            94: ['RedRepOn', (176,176,176), [147]*6, 'xdcircuit', 'onehigh'],	#TODO 'redrep' meshtype
            95: ['LockedChest', (164,114,39), [25,25,26,27,26,26], 'xd', 'chest'], #texface order wrong (see #54)
            96: ['Trapdoor', (117,70,34), [84]*6, 'XD', 'inset', [0,13,0]],
            97: ['HiddenSfish', (116,116,116), [1]*6],
            98: ['StoneBricks', (100,100,100), [54]*6, 'XD'],
            99: ['HgBrwM', (210,177,125), [142]*6, 'XD'],	#XD for part/variant/colour (stalk/main)
            100: ['HgRedM', (210,177,125), [142]*6, 'XD'],
            101: ['IronBars', (171,171,173), [85]*6, 'XD', 'pane'],
            102: ['GlassPane', (254,254,254), [49]*6, 'XD', 'pane', None, {'transp': True}],
            103: ['Melon', (166,166,39), [137,137,136,136,136,136]],
            104: ['PumpkinStem'],
            105: ['MelonStem'],
            106: ['Vines', (39,98,13), [143]*6, 'XD', 'wallface'],
            107: ['FenceGate', (143,115,73)],
            108: ['BrickStairs', (135,74,58), [7]*6, 'XD', 'stairs'],
            109: ['StoneBrickStairs', (100,100,100), [54]*6, 'XD', 'stairs'],
            110: ['Mycelium', (122,103,108), [2,78,77,77,77,77]],	#useful to ignore option? as this is Dirt top in Mushroom Biomes.
            111: ['LilyPad', (12,94,19), [76]*6, 'none', 'onehigh', None, {'transp': True}],
            112: ['NethrBrick', (48,24,28), [224]*6],
            113: ['NethrBrickFence', (48,24,28), [224]*6, 'XD', 'fence'],
            114: ['NethrBrickStairs', (48,24,28), [224]*6, 'XD', 'stairs'],
            115: ['NethrWart', (154,39,52), [226]*6],
            116: ['EnchantTab', (116,30,29), [167,166,182,182,182,182], 'none', 'inset', [0,4,0]],  #TODO enchantable with book?
            117: ['BrewStnd', (207,227,186), [157]*6, 'x', 'brewstand'],    #fully custom model
            118: ['Cauldron', (55,55,55), [139,138,154,154,154,154]],  #fully custom model
            119: ['EndPortal', (0,0,0), None],
            120: ['EndPortalFrame', (144,151,110), [175,158,159,159,159,159]],
            121: ['EndStone', (144,151,110), [175]*6],
            122: ['DragonEgg', (0,0,0)],
            123: ['RedstLampOff', (140,80,44), [211]*6],
            124: ['RedstLampOn',  (247,201,138), [212]*6]
            }
    #Add in the rest!
    #Need to manually set textures and materials for each of these! damn!


BLOCKVARIANTS = {

#sapling: 6 -- spruce, birch and jungle types

                  6:  [ [''],
                        ['Spruce', (57,90,57), [63]*6],
                        ['Birch', (207,227,186), [79]*6],
                        ['Jungle', (57,61,13), [30]*6]
                      ],

                  17: [ [''],#normal wood (oak)
                        ['Spruce',(76,61,38), [21,21,116,116,116,116]],
                        ['Birch', (76,61,38), [21,21,117,117,117,117]],
                        ['Jungle',(89,70,27), [21,21,153,153,153,153]],
                      ],
#adjust leaf types, too!
                    
                  24: [ [''],#normal 'cracked' sandstone
                        ['Decor', (215,209,153), [176,176,229,229,229,229]],
                        ['Smooth',(215,209,153), [176,176,230,230,230,230]],
                      ],

                  35: [ [''],
                        ['Orange', (255,150,54), [210]*6],	#custom tex coords!
                        ['Magenta', (227,74,240), [194]*6],
                        ['LightBlue', (83,146,255), [178]*6],
                        ['Yellow', (225,208,31), [162]*6],
                        ['LightGreen', (67,218,53), [146]*6],
                        ['Pink', (248,153,178), [130]*6],
                        ['Grey', (75,75,75), [114]*6],
                        ['LightGrey', (181,189,189), [225]*6],
                        ['Cyan', (45,134,172), [209]*6],
                        ['Purple', (134,53,204), [193]*6],
                        ['Blue', (44,58,176), [177]*6],
                        ['Brown', (99,59,32), [161]*6],
                        ['DarkGreen', (64,89,27), [145]*6],
                        ['Red', (188,51,46), [129]*6],
                        ['Black', (28,23,23), [113]*6]
                      ],
                  #doubleslabs
                  43: [ [''], #stone slabs (default)
                        ['SndStn', (215,209,153), [192]*6],
                        ['Wdn', (159,132,77), [4]*6],
                        ['Cobl', (94,94,94), [16]*6],
                        ['Brick', (124,69,24), [7]*6],
                        ['StnBrk', (100,100,100), [54]*6],
                        [''],
                      ],
                  
                  #slabs
                  44: [ [''], #stone slabs (default)
                        ['SndStn', (215,209,153), [192]*6],
                        ['Wdn', (159,132,77), [4]*6],
                        ['Cobl', (94,94,94), [16]*6],
                        ['Brick', (124,69,24), [7]*6],
                        ['StnBrk', (100,100,100), [54]*6],
                        [''],
                      ],
                      
                  50: [ [''], #nowt on 0...
                        ['Ea'],	#None for colour, none Tex, then: CUSTOM MESH
                        ['We'],
                        ['So'],
                        ['Nr'],
                        ['Up']
                      ],
                      
                  #stone brick moss/crack/circle variants:
                  98: [ [''],
                        ['Mossy',  (100,100,100), [100]*6],
                        ['Cracked',(100,100,100), [101]*6],
                        ['Circle', (100,100,100), [213]*6],
                      ],
                  #hugebrownmush:
                  99: [ [''], #default (pores on all sides)
                        ['CrTWN',(210,177,125),[142,126,142,142,126,126]],#1
                        ['SdTN',(210,177,125),[142,126,142,142,142,126]],#2
                        ['CrTEN',(210,177,125),[142,126,126,142,142,126]],#3
                        ['SdTW',(210,177,125),[142,126,142,142,126,142]],#4
                        ['Top',(210,177,125),[142,126,142,142,142,142]],#5
                        ['SdTE',(210,177,125),[142,126,126,142,142,142]],#6
                        ['CrTSW',(210,177,125),[142,126,142,126,126,142]],#7
                        ['SdTS',(210,177,125),[142,126,142,126,142,142]],#8
                        ['CrTES',(210,177,125),[142,126,126,126,142,142]],#9
                        ['Stem',(215,211,200),[142,142,141,141,141,141]]#10
                      ],
                  #hugeredmush:
                  100:[ [''], #default (pores on all sides)
                        ['CrTWN',(188,36,34),[142,125,142,142,125,125]],#1
                        ['SdTN',(188,36,34),[142,125,142,142,142,125]],#2
                        ['CrTEN',(188,36,34),[142,125,125,142,142,125]],#3
                        ['SdTW',(188,36,34),[142,125,142,142,125,142]],#4
                        ['Top',(188,36,34),[142,125,142,142,142,142]],#5
                        ['SdTE',(188,36,34),[142,125,125,142,142,142]],#6
                        ['CrTSW',(188,36,34),[142,125,142,125,125,142]],#7
                        ['SdTS',(188,36,34),[142,125,142,125,142,142]],#8
                        ['CrTES',(188,36,34),[142,125,125,125,142,142]],#9
                        ['Stem',(215,211,200),[142,142,141,141,141,141]]#10
                      ]
}


def readLevelDat():
    """Reads the level.dat for info like the world name, player inventory..."""
    lvlfile = gzip.open('level.dat', 'rb')

    #first byte must be a 10 (TAG_Compound) containing all else.
    #read a TAG_Compound...
    #rootTag = Tag(lvlfile)

    rootTag = nbtreader.TagReader.readNamedTag(lvlfile)[1]    #don't care about the name... or do we? Argh, it's a named tag. Stick the name IN the tag after reading?

    print(rootTag.printTree(0))    #give it repr with an indent param...?


def readRegion(fname, vertexBuffer):
    
    #A region has an 8-KILObyte header, containing 1024 locations and 1024 timestamps. Then from 8196 onwards, it's chunk data and (arbitrary?) gaps
    #Chunks are zlib compressed and have their own structure... more on that later.
    print('== Reading region %s ==' % fname)
    
    rfile = open(fname, 'rb')
    
    regionheader = rfile.read(8192)

    chunklist = []
    chunkcount = 0
    
    cio = 0    #chunk index offset
    while cio+4 <= 4096:    #only up to end of the locations! (After that is timestamps)
        cheadr = regionheader[cio:cio+4]
        
        # 3 bytes "offset"            -- how many 4kiB disk sectors away the chunk data is from the start of the file.
        # 1 byte "sector count"    -- how many 4kiB disk sectors long the chunk data is. (this figure is rounded up during save, so this will give the last disk sector in which there's data for this chunk)

        offset = unpack(">i", b'\x00'+cheadr[0:3])[0]
        chunksectorcount = cheadr[3]    #last of the 4 bytes is the size (in 4k sectors) of the chunk
        
        chunksLoaded = 0
        if offset != 0 and chunksectorcount != 0:    #chunks not generated as those coordinates yet will be blank!
            chunkdata = readChunk(rfile, offset, chunksectorcount)    #TODO Make sure you seek back to where you were to start with ...
            chunksLoaded += 1
            chunkcount += 1

            #print(chunkdata.printTree(0))
            #quit()
            chunklist.append((offset,chunksectorcount))
    #within the header, work out how many chunks are there... check timestamps... and then jump to chunk...
        cio += 4

    rfile.close()

    print("Region file %s contains %d chunks." % (fname, chunkcount))
    return chunkcount


def toChunkPos(pX,pZ):
    return (pX/16, pZ/16)


#TODO Possible Key Options for the importer:
#"Surface only": use the heightmap and only load surface.
#Load more than just the top level, obviously, cos of cliff 
#walls, caves, etc. water should count as transparent for this process, as should glass, portal, and all nonsolid block types.
# cliffs will also need more loading,should there be overhangs.
#from side-by-side drops in surface value

#"Load horizon" / "load radius": how far away from the load point should 
#the loading continue? Can't possibly load everything in big worlds.


def batchBuild(meshBuffer):
    #build all geom from pydata as meshes in one shot. :) This is fast.
    for meshname in (meshBuffer.keys()):
        me = bpy.data.meshes[meshname]
        me.from_pydata(meshBuffer[meshname], [], [])
        me.update()


def mcToBlendCoord(chunkPos, blockPos):
    """Converts a minecraft chunk X,Z pair and a minecraft ordered X,Y,Z block location triple into a Blender coordinate vector Vx,Vy,Vz.
And remember: in Minecraft, Y points to the sky."""
    
    # Mapping Minecraft coords -> Blender coords
    # In Minecraft, +Z (west) <--- 0 ----> -Z (east), while North is -X and South is +X
    # In Blender, north is +Y, south is-Y, west is -X and east is +X.
    # So negate Z and map it as X, and negate X and map it as Y. It's slightly odd!

    vx = -(chunkPos[1] << 4) - blockPos[2]
    vy = -(chunkPos[0] << 4) - blockPos[0]   # -x of chunkpos and -x of blockPos (x,y,z)
    vz = blockPos[1]    #Minecraft's Y.
    
    return Vector((vx,vy,vz))


def getMCBlockType(blockID, extraBits):
    """Gets reference to a block type mesh, or creates it if it doesn't exist.
The mesh created depends on meshType from the global blockdata (whether it's torch or repeater, not a cube)
These also have to be unique and differently named for directional versions of the same thing - eg track round a corner or up a slope.
This also ensures material and name are set."""
    from . import blockbuild
    global OPTIONS  #, BLOCKDATA (surely!?)

    bdat = BLOCKDATA[blockID]

    corename = bdat[0]    # eg mcStone, mcTorch

    if len(bdat) > 1:
        colourtriple = bdat[1]
    else:
        colourtriple = [214,127,255] #shocking pink

    mcfaceindices = []
    if len(bdat) > 2 and bdat[2] is not None:
        mcfaceindices = bdat[2]

    usesExtraBits = False
    if len(bdat) > 3:
        usesExtraBits = (bdat[3] == 'XD')

    if not usesExtraBits:	#quick early create...
        landmeshname = "".join(["mc", corename])
        if landmeshname in bpy.data.meshes:
            return bpy.data.meshes[landmeshname]
        else:
            extraBits = None

    objectShape = "box"	#but this can change based on extra data too...
    if len(bdat) > 4:
        objectShape = bdat[4]

    shapeParams = None
    if len(bdat) > 5:   #and objectShape = 'insets'
        shapeParams = bdat[5]
    
    cycParams = None
    if OPTIONS['usecycles']:
        if len(bdat) > 6:
            cycParams = bdat[6]
        if cycParams is None:
            cycParams = {'emit': 0.0, 'transp': False}
    
    nameVariant = ''
    if blockID in BLOCKVARIANTS:
        variants = BLOCKVARIANTS[blockID]
        if extraBits is not None and extraBits >= 0 and extraBits < len(variants):
            variantData = variants[extraBits]
            if len(variantData) > 0:
                nameVariant = variantData[0]
                #print("%d Block uses extra data: {%d}. So name variant is: %s" % (blockID, extraBits, nameVariant))
                #Now apply each available variant datum: colour triple, texture faces, and blockbuild variation.
                if len(variantData) > 1:	#read custom RGB
                    colourtriple = variantData[1]
                    if len(variantData) > 2:
                        mcfaceindices = variantData[2]
                        #mesh constructor...
    corename = "".join([corename, nameVariant])
    meshname = "".join(["mc", corename])

    dupblock = blockbuild.construct(blockID, corename, colourtriple, mcfaceindices, extraBits, objectShape, shapeParams, cycParams)	#creates the mesh, no matter what.
    #nb: construct should QUICKLY determine the exact thing it needs to make, and then CHECK if it already exists.

    blockname = dupblock.name
    landmeshname = "".join(["mc", blockname.replace('Block', '')])

    if landmeshname in bpy.data.meshes:
        return bpy.data.meshes[landmeshname]

    landmesh = bpy.data.meshes.new(landmeshname)
    landob = bpy.data.objects.new(landmeshname, landmesh)
    bpy.context.scene.objects.link(landob)

    global WORLD_ROOT	#will have been created by this point. Just parent the land to it. (a bit messy, but this is a small-scope script)
    landob.parent = WORLD_ROOT

    #dupBlockOb = blockbuild.createMCBlock(typename, colourtriple, mcfaceindices)	# (bottom, top, right, front, left, back!)

    dupblock.parent = landob
    landob.dupli_type = "VERTS"
    return landmesh


def slimeOn():
    """Creates the cloneable slime block (area marker) and a mesh to duplivert it."""
    if 'slimeChunks' in bpy.data.objects:
        return

    #Create cube! (maybe give it silly eyes...)
    #ensure 3d cursor at 0...
    
    bpy.ops.mesh.primitive_cube_add()
    slimeOb = bpy.context.object    #get ref to last created ob.
    slimeOb.name = 'slimeMarker'
    bpy.ops.transform.resize(value=(8, 8, 8))
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    #slimeMarkerMesh = slimeOb.data	# could use this to 
    # make it chunk-sized... starts 2x2x2
    
    # create material for the markers
    slimeMat = None
    smname = "mcSlimeMat"
    if smname in bpy.data.materials:
        slimeMat = bpy.data.materials[smname]
    else:
        slimeMat = bpy.data.materials.new(smname)
        slimeMat.diffuse_color = [86/256.0, 139.0/256.0, 72.0/256.0]
        slimeMat.diffuse_shader = 'OREN_NAYAR'
        slimeMat.diffuse_intensity = 0.8
        slimeMat.roughness = 0.909
        #slimeMat.use_shadeless = True	#traceable false!!
        slimeMat.use_transparency = True
        slimeMat.alpha = .25
        #slimeMat.use_face_texture = True
        #slimeMat.use_face_texture_alpha = True

    slimeOb.data.materials.append(slimeMat)
    slimeChunkmesh = bpy.data.meshes.new("slimeChunks")
    slimeChunkob = bpy.data.objects.new("slimeChunks", slimeChunkmesh)
    bpy.context.scene.objects.link(slimeChunkob)
    slimeOb.parent = slimeChunkob
    slimeChunkob.dupli_type = "VERTS"
    global WORLD_ROOT
    slimeChunkob.parent = WORLD_ROOT



def batchSlimeChunks(slimes):
    #build all slime marker instances to their dupli-geom from pydata as meshes in one shot. :(
    me = bpy.data.meshes["slimeChunks"]
    me.from_pydata(slimes, [], [])
    me.update()



def getWorldSelectList():
    worldList = []
    if os.path.exists(MCSAVEPATH):
        startpath = os.getcwd()
        os.chdir(MCSAVEPATH)
        saveList = os.listdir()
        saveFolders = [f for f in saveList if os.path.isdir(f)]
        wcount = 0
        for sf in saveFolders:
            if os.path.exists(sf + "/level.dat"):
                #read actual world name(not just folder name)
                wData = None
                try:
                    with gzip.open(sf + '/level.dat', 'rb') as levelDat:
                        wData = nbtreader.readNBT(levelDat)
                        ##catch errors if level.dat wasn't a gzip...
                except IOError:
                    print("Unknown problem with level.dat format for %s" % sf)
                    continue
                wname = wData.value['Data'].value['LevelName'].value
                wsize = wData.value['Data'].value['SizeOnDisk'].value
                readableSize = "(%0.1f)" % (wsize / (1024*1024))
                worldList.append((sf, sf, wname + " " + readableSize))
                wcount += 1
        os.chdir(startpath)

    if worldList != []:
        return worldList
        #itemlist = []
        #for n, wname in enumerate(worldList):
        #    itemlist.append((str(n), os.path.join(MCSAVEPATH,wname), wname))
        #return itemlist
    else:
        return None


def hasNether(worldFolder):
    #print("checking has nether: [%s]" % (worldFolder))
    #print ("end check:")
    #print(worldFolder)
    if worldFolder == "":
        return False
    worldList = []
    if os.path.exists(MCSAVEPATH):
        worldList = os.listdir(MCSAVEPATH)
        if worldFolder in worldList:
            wp = os.path.join(MCSAVEPATH, worldFolder, 'DIM-1')
            return os.path.exists(wp)   #and contains correct files... (could also check regions aren't empty, etc)
    return False

def hasEnd(worldFolder):
    #print("checking has end: [%s]" % (worldFolder))
    #print ("end check:")
    #print(worldFolder)
    if worldFolder == "":
        return False
    worldList = []
    if os.path.exists(MCSAVEPATH):
        worldList = os.listdir(MCSAVEPATH)
        if worldFolder in worldList:
            wp = os.path.join(MCSAVEPATH, worldFolder, 'DIM1')
            return os.path.exists(wp)   #and contains correct files... (could also check regions aren't empty, etc)
    return False

def readMinecraftWorld(worldFolder, loadRadius, toggleOptions):
    global unknownBlockIDs, wseed
    global EXCLUDED_BLOCKS
    global WORLD_ROOT
    global OPTIONS, REPORTING
    OPTIONS = toggleOptions

    #timing/profiling:
    global tChunkReadTimes

    if worldFolder == "":
        #world selected was blank. This can only happen if world select list was empty, ie no saves.
        print("No valid saved worlds were available to load.")
        return

#    print("[!] OmitStone: ", toggleOptions['omitstone'])
    if not OPTIONS['omitstone']:
        EXCLUDED_BLOCKS = []

#    print('[[[exluding these blocks: ', EXCLUDED_BLOCKS, ']]]')
    worldList = []

    if os.path.exists(MCSAVEPATH):
        worldList = os.listdir(MCSAVEPATH)
        print("MC Path exists! %s" % os.listdir(MCPATH))
        #wherever os was before, save it,and restore it after this completes.
        os.chdir(MCSAVEPATH)

    worldSelected = worldFolder

    os.chdir(os.path.join(MCSAVEPATH, worldSelected))

    # If there's a folder DIM-1 in the world folder, you've been to the Nether!
    # ...And generated Nether regions.
    if os.path.exists('DIM-1'):
        if OPTIONS['loadnether']:
            print('nether LOAD!')
        else:
            print('Nether is present, but not chosen to load.')
    
    if os.path.exists('DIM1'):
        if OPTIONS['loadend']:
            print('load The End...')
        else:
            print('The End is present, but not chosen to load.')

    #if the player didn't save out in those dimensions, we HAVE TO load at 3D cursor (or 0,0,0)

    worldData = None
    pSaveDim = None
    worldFormat = 'mcregion'	#assume initially

    with gzip.open('level.dat', 'rb') as levelDat:
        worldData = nbtreader.readNBT(levelDat)
    #print(levelStats.printTree(0))

    #Check if it's a multiplayer saved game (which has been moved to saves dir)
    #These don't have the Player tag.
    if 'Player' in worldData.value['Data'].value:
        #It's singleplayer
        pPos = [posFloat.value for posFloat in worldData.value['Data'].value['Player'].value['Pos'].value ]     #in NBT, there's a lot of value...
        pSaveDim = worldData.value['Data'].value['Player'].value['Dimension'].value
    else:
        #It's multiplayer.
        #Get SpawnX, SpawnY, SpawnZ and centre around those. OR
        #TODO: Check for another subfolder: 'players'. Read each NBT .dat in there, and create empties for all of them, but load around the first one.
        spX = worldData.value['Data'].value['SpawnX'].value
        spY = worldData.value['Data'].value['SpawnY'].value
        spZ = worldData.value['Data'].value['SpawnZ'].value
        pPos = [float(spX), float(spY), float(spZ)]
        
        #create empty markers for each player.
    
    if 'version' in worldData.value['Data'].value:
        fmtVersion = worldData.value['Data'].value['version'].value	#19133 for Anvil. 19132 is McRegion.
        if fmtVersion == MCREGION_VERSION_ID:
            print("World is in McRegion format")
        elif fmtVersion == ANVIL_VERSION_ID:
            print("World is in Anvil format")
            worldFormat = "anvil"

    wseed = worldData.value['Data'].value['RandomSeed'].value	#it's a Long
    print("World Seed : %d" % (wseed))	# or self.report....

    #print("Player is at : %0.4f %0.4f %0.4f" % (pPos[0], pPos[1], pPos[2]))
    #retrieve player location from worldstats:
    
    #if LOAD_AROUND_3D_CURSOR:
    if (OPTIONS['loadnether'] and (pSaveDim is None or int(pSaveDim) != -1)) or OPTIONS['atcursor']:
        cursorPos = bpy.context.scene.cursor_location
        #that's an x,y,z vector (in Blender coords)
        #convert to insane Minecraft coords!        ##todo: test and check this still works in anvil??!
        # mcraft pos = -Y, Z, -X
        pPos = [ -cursorPos[1], cursorPos[2], -cursorPos[0]]

    if OPTIONS['loadnether']:
        os.chdir(os.path.join("DIM-1", "region"))
    elif OPTIONS['loadend']:
        os.chdir(os.path.join("DIM1", "region"))
    else:
        os.chdir("region")

    meshBuffer = {}

    #Initialise the world root - an empty to parent all land objects to.
    WORLD_ROOT = bpy.data.objects.new(worldSelected, None)	#EMPTY! By name of "worldSelected"
    bpy.context.scene.objects.link(WORLD_ROOT)
    WORLD_ROOT.empty_draw_size = 2.0
    WORLD_ROOT.empty_draw_type = 'SPHERE'
    
    regionfiles = []
    regionreader = None
    if worldFormat == 'mcregion':
        regionfiles = [f for f in os.listdir() if f.endswith('.mcr')]
        from .mcregionreader import ChunkReader
        regionreader = ChunkReader()  #just the class, not an instance...?
        
        #for r in regionfiles:
        #    print("Reading: %s" % r)
        #    totalchunks += readRegion(r)	#bad! We should read all chunks that might be present. Never mind 'regions'.
    elif worldFormat == 'anvil':
        regionfiles = [f for f in os.listdir() if f.endswith('.mca')]
        from .mcanvilreader import AnvilChunkReader
        regionreader = AnvilChunkReader()
        #for r in regionfiles:
        #    print("Reading: %s" % r)
        #    totalchunks += readAnvilRegion(r, noisy=True)	#bad! We should read all chunks that might be present. Never mind 'regions'.
    ####regionfiles = os.listdir() nope!

    #except when loading nether...
    playerChunk = toChunkPos(pPos[0], pPos[2])  # x, z
    
    print("Loading %d blocks around centre." % loadRadius)
    #loadRadius = 10 #Sane amount: 5 or 4. See also: 'load all' project... omit data below y-level 40. etc. other restriction options.
    #load stone...

    if not OPTIONS['atcursor']:	#loading at player
        #Add an Empty to show where the player is. (+CENTRE CAMERA ON!)
        playerpos = bpy.data.objects.new('PlayerLoc', None)
        #set its coordinates...
        #convert Minecraft coordinate position of player into Blender coords:
        playerpos.location[0] = -pPos[2]
        playerpos.location[1] = -pPos[0]
        playerpos.location[2] = pPos[1]
        bpy.context.scene.objects.link(playerpos)
        playerpos.parent = WORLD_ROOT

    #total chunk count across region files:
    REPORTING['totalchunks'] = 0
    
    pX = int(playerChunk[0])
    pZ = int(playerChunk[1])
    
    print('Loading a radius of %d chunks around load position, so creating chunks: %d,%d to %d,%d' % (loadRadius, pX-loadRadius, pZ-loadRadius, pX+loadRadius, pZ+loadRadius))

    if (OPTIONS['showslimes']):
        slimeOn()	# if set in options...
        from . import slimes
        slimeBuffer = []

    for z in range(pZ-loadRadius, pZ+loadRadius):
        for x in range(pX-loadRadius, pX+loadRadius):

            tChunk0 = datetime.datetime.now()
            regionreader.readChunk(x,z, meshBuffer) #may need to be further broken down to block level. maybe rename as loadChunk.
            tChunk1 = datetime.datetime.now()
            chunkTime = tChunk1 - tChunk0
            tChunkReadTimes.append(chunkTime.total_seconds())	#tString = "%.2f seconds" % chunkTime.total_seconds() it's a float.

            if (OPTIONS['showslimes']):
                if slimes.isSlimeSpawn(wseed, x, z):
                    slimeLoc = mcToBlendCoord((x,z), (8,8,8))	#(8,8,120)
                    slimeLoc += Vector((0.5,0.5,-0.5))
                    slimeBuffer.append(slimeLoc)

    tBuild0 = datetime.datetime.now()
    batchBuild(meshBuffer)
    if (OPTIONS['showslimes']):
        batchSlimeChunks(slimeBuffer)
    tBuild1 = datetime.datetime.now()
    tBuildTime = tBuild1 - tBuild0
    print("Built meshes in %.2fs" % tBuildTime.total_seconds())

    #all meshes.update()!

    #Load all chunks in a region (Noooo!)

#    firstRegion = regionfiles[0]
#    regionChunks = readRegion(firstRegion, vertexBuffer)
#    totalchunks += regionChunks
    #for r in regionfiles:
    #    print("Reading: %s" % r)
    #    totalchunks += readRegion(r)

        #print(rdat.printTree(0))
    print("%s: loaded %d chunks" % (worldSelected, totalchunks))
    if len(unknownBlockIDs) > 0:
        print("Unknown new Minecraft datablock IDs encountered:")
        print(" ".join(["%d" % bn for bn in unknownBlockIDs]))
    
    #Viewport performance hides:
    hideIfPresent('mcStone')
    hideIfPresent('mcDirt')
    hideIfPresent('mcSandstone')
    hideIfPresent('mcIronOre')
    hideIfPresent('mcGravel')
    hideIfPresent('mcCoalOre')
    hideIfPresent('mcBedrock')
    hideIfPresent('mcRedstoneOre')

    #Profile/run stats:
    chunkReadTotal = tChunkReadTimes[0]
    for tdiff in tChunkReadTimes[1:]:
        chunkReadTotal = chunkReadTotal + tdiff
    print("Total chunk reads time: %.2fs" % chunkReadTotal)  #I presume that's in seconds, ofc... hm.
    chunkMRT = chunkReadTotal / len(tChunkReadTimes)
    print("Mean chunk read time: %.2fs" % chunkMRT)
    
    print("Block points processed: %d" % REPORTING['blocksread'])
    print("of those, verts dumped: %d" % REPORTING['blocksdropped'])
    if REPORTING['blocksread'] > 0:
        print("Difference (expected vertex count): %d" % (REPORTING['blocksread'] - REPORTING['blocksdropped']))
        print("Hollowing has made the scene %d%% lighter" % ((REPORTING['blocksdropped'] / REPORTING['blocksread']) * 100))
    
    
    #increase viewport clipping distance to see the world! (or maybe decrease mesh sizes)
    #bpy.types.Space...
    

def hideIfPresent(mName):
    if mName in bpy.data.objects:
        bpy.data.objects[mName].hide = True


def makeCube(scale, meshname, obname):
    scale_x = scale[0]
    scale_y = scale[1]
    scale_z = scale[2]

    x1 = -0.5 * scale_x
    x2 = 0.5 * scale_x
    y1 = -0.5 * scale_y
    y2 = 0.5 * scale_y
    z1 = -0.5 * scale_z
    z2 = 0.5 * scale_z

    verts = [Vector((x1, y2, z1)),
             Vector((x2, y2, z1)),
             Vector((x2, y1, z1)),
             Vector((x1, y1, z1)),

             Vector((x1, y2, z2)),
             Vector((x2, y2, z2)),
             Vector((x2, y1, z2)),
             Vector((x1, y1, z2)),
            ]

    edges = []
    faces = [[0, 1, 2, 3], [7,6,5,4], #top and bot
    [3,0,4,7], [4,0,1,5], [6,2,1,5], [7,3,2,6]] #sides

    #Adding UV data... how! (try something in mesh.uv_...
    #see bpy.ops.mesh.uv_... or object.uv..
    #    # see bpy.ops.mesh.uv_texture_add()
    
    mesh = bpy.data.meshes.new(meshname)
    mesh.from_pydata(verts, edges, faces)
    
    stoneblockObj = bpy.data.objects.new(obname, mesh)

    #And add the Block into the current blender scene. Could do layers = [array of bool] to set it properly. Remember [False]*32 or whatever it is...
    bpy.context.scene.objects.link(stoneblockObj)

    return stoneblockObj



def add_object(self, context):
    
    # Create the Block (to be instanced)
    
    scale_x = self.scale.x
    scale_y = self.scale.y
    scale_z = self.scale.z

    makeCube((scale_x, scale_y, scale_z), meshname, obname)

    #
    # Create the datagrid for where the blocks will appear (this will later be properly generated by the Minecraft data file...
    #

    #but can the pydata create all the verts needed? :D HELL YES! Immediately!
    meshstone = bpy.data.meshes.new('Chunkgrid.Stone')

    #create the 16x16 bit once, then replicate but change the Z??
    vx = []
    for nx in range(16):
        for ny in range(16):
            for nz in range(128):
                vx.append(Vector((nx,ny,nz)))

    meshstone.from_pydata(vx, [], [])   #no edges. No faces.

    gridObj = bpy.data.objects.new("ChunkgridStone", meshstone)
    
    bpy.context.scene.objects.link(gridObj)
   
    
    # useful for development when the mesh may be invalid.
    # mesh.validate(verbose=True)
    
    
    #where do we want the origin to be?
    #nope! Make these VERTS, instead.
    #potentially precalculate each vert pos, too!
    
    #bpy.data.groups.new("Replicant")    #we dupli this all over the new mesh...
    #create a new object, add it to the replicant group.
    
    #create the replicant mesh / object. Name it.
    #Clear its position to 0,0,0
    #Parent it to the volumegrid mesh. Like this:
    
    #create the cube myself in order to fiddle its UVs and texture it as a minecraft block type... probably. Or create cube and then jimmy around with its textures.
    
    
    stoneblockObj.parent = gridObj  #set parentage...
    gridObj.dupli_type = "VERTS"    #instantiate EVERYTHING, Ho!

    
    #switch volumegrid to:
    
    #bpy.data.objects['Icosphere'].dupli_type = "VERTS"
    

#nb: bpy.data.groups.remove(bpy.data.groups["MonkeyGroup.001"])

    #nb if you try creating the same group twice,
    #the second one gets created as name.001

#No no no!
#    for xplace in range(16):
#         for yplace in range(16):
#            for zplace in range(128):
#                add_object_data(context, mesh, operator=self)
#                #can add this not as duplicate, but instance?
#                bpy.ops.transform.translate(value=(xplace,yplace,zplace))

    #add_object_data(context, mesh, operator=self)
    #bpy.ops.transform.translate(value=(1,1,1))



#class OBJECT_OT_add_object(bpy.types.Operator, AddObjectHelper):	#don't extend 'add object' helper, use file import helper or something similar....
#    """Add a Minecraft Chunk Test Object"""
#    bl_idname = "mesh.add_mcchunk"
#    bl_label = "Add Minecraft Chunk"
#    bl_description = "Create a new Minecraft Chunk"
#    bl_options = {'REGISTER', 'UNDO'}
#
#    scale = FloatVectorProperty(name='scale',
#                                default=(1.0, 1.0, 1.0),
#                                subtype='TRANSLATION',
#                                description='scaling')
#
#    def execute(self, context):
#        #At execution time, rather than otherwise,
#        #dynamically define the output
#
#        #for y in range(128):
#        
#        #Actual original version:
#        #add_object(self, context)
#        readMinecraftWorld(self,context)
#
#        return {'FINISHED'}
#

# Feature TODOs
# surface load (skin only, not block instances)
# torch, stairs, rails, redrep meshblocks. flowers/shrooms.
# nether load
# mesh optimisations
# multiple loads per run -- need to name new meshes each time load performed, ie mcGrass.001
# ...
