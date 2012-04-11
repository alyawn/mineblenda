import bpy
from mathutils import *
import os, sys

#create class for the other functions? BlockBuilder.

#NICEIF: SpaceView3D.grid_subdivisions = 16 (so they're MC pixel-based)

#TODO: tidy this up to one location (double defined here from mineregion)
MCPATH = ''
if sys.platform == 'darwin':
    MCPATH = os.path.join(os.environ['HOME'], 'Library', 'Application Support', 'minecraft')
elif sys.platform == 'linux2':
    MCPATH = os.path.join(os.environ['HOME'], '.minecraft')
else:
    MCPATH = os.path.join(os.environ['APPDATA'], '.minecraft')
# This needs to be set by the addon during initial inclusion. Set as a bpy.props.StringProperty within the Scene, then refer to it all over this addon.

#class BlockBuilder:
#    """Defines methods for creating whole-block Minecraft blocks with correct texturing - just needs minecraft path."""

def construct(blockID, basename, diffuseRGB, cubeTexFaces, extraData, constructType="box", shapeParams=None, cycParams=None):
    # find block function/constructor that matches the construct type.
    
    #if it's a simple cube...
    #stairs
    #onehigh
    #torch
    
    ##TODO: New type: INSET-BOX. It's a cube, but with inset XYZ's and UVs. :) Covers MANY MC Objects,
    #including torch.
    
    block = None
    if constructType == 'box':
        block = createMCBlock(basename, diffuseRGB, cubeTexFaces, cycParams)	#extra data
    elif constructType == 'onehigh':
        block = createInsetMCBlock(basename, diffuseRGB, cubeTexFaces, [0,15,0], cycParams)
    elif constructType == '00track':
        block = createTrack(basename, diffuseRGB, cubeTexFaces, extraData, cycParams)
    elif constructType == 'inset':  #make an inset box (requires shapeParams)
        block = createInsetMCBlock(basename, diffuseRGB, cubeTexFaces, shapeParams, cycParams) #shapeprms must be a 3-list
    else:
        block = createMCBlock(basename, diffuseRGB, cubeTexFaces, cycParams)	#extra data	# soon to be removed as a catch-all!
    return block


def getMCTex():
    tname = 'mcTexBlocks'
    if tname in bpy.data.textures:
        return bpy.data.textures[tname]

    print("creating fresh new minecraft terrain texture")
    texNew = bpy.data.textures.new(tname, 'IMAGE')
    texNew.image = getMCImg()
    texNew.image.use_premultiply = True
    texNew.use_alpha = True
    texNew.use_preview_alpha = True
    texNew.use_interpolation = False
    texNew.filter_type = 'BOX'    #no AA - nice minecraft pixels!

def getMCImg():
    global MCPATH
    osdir = os.getcwd()	#original os folder before jumping to temp.
    if 'terrain.png' in bpy.data.images:
        return bpy.data.images['terrain.png']
    else:
        img = None
        import zipfile
        mcjar = os.path.sep.join([MCPATH, 'bin', 'minecraft.jar'])
        zf = open(mcjar, 'rb')
        zipjar = zipfile.ZipFile(zf)
        if 'terrain.png' in zipjar.namelist():
            os.chdir(bpy.app.tempdir)
            zipjar.extract('terrain.png')
        zipjar.close()
        zf.close()  #needed?
            #
        temppath = os.path.sep.join([os.getcwd(), 'terrain.png'])
        try:
            img = bpy.data.images.load(temppath)
        except:
            os.chdir(osdir)
            raise NameError("Cannot load image %s" % temppath)
        os.chdir(osdir)
        return img


def getCyclesMCImg():
    #Ideally, we want a very large version of terrain.png to hack around
    #cycles' inability to give us control of Alpha in 2.61
    #However, for now it just gives a separate instance of the normal one that
    #will need to be scaled up manually (ie replace this image to fix all transparent noodles)
    
    if 'hiResTerrain.png' not in bpy.data.images:
        im1 = None
        if 'terrain.png' not in bpy.data.images:
            im1 = getMCImg()
        else:
            im1 = bpy.data.images['terrain.png']

        #Create second version/instance of it.
        im2 = im1.copy()
        im2.name = 'hiResTerrain.png'
        #scale that up / modify... somehow?
        
    return bpy.data.images['hiResTerrain.png']




def createBlockCubeUVs(blockname, me, matrl, faceIndices):    #assume me is a cube mesh.  RETURNS **NAME** of the uv layer created.
    __listtype = type([])
    if type(faceIndices) != __listtype:
        if (type(faceIndices) == type(0)):
            faceIndices = [faceIndices]*6
            print("Applying singular value to all 6 faces")
        else:
            print("setting material and uvs for %s: non-numerical face list" % blockname)
            print(faceIndices)
            raise IndexError("improper face assignment data!")


    #now, assume we have a list of per-face block IDs.
    #faceindices should be an array of minecraft material indices (into the terrain.png) with what texture should be used for each face. Face order is [Bottom,Top,Right,Front,Left,Back]

    uname = blockname + 'UVs'

    blockUVLayer = me.uv_textures.new(uname)   #assuming it's not so assigned already, ofc.

    #get image reference (from the material texture...?)
    xim = getMCImg()

    #ADD THE MATERIAL!
    if matrl.name not in me.materials:
        me.materials.append(matrl)

    meshtexfaces = blockUVLayer.data.values()
    
    matrl.game_settings.alpha_blend = 'CLIP'
    matrl.game_settings.use_backface_culling = False
    
    for fnum, fid in enumerate(faceIndices):
        face = meshtexfaces[fnum]

        face.image = xim
        #face.blend_type = 'ALPHA'	# set per-material as of 2.60 -- need to fix this.
        ## now use instead: matrl.game_settings.alpha_blend = 'ALPHA_CLIP'
        #use_image

        #Pick UV square off the 2D texture surface based on its Minecraft texture 'index'
        #eg 160 for lapis, 49 for glass... etc, etc.
        # that's x,y:
    
        mcTexU = fid % 16
        mcTexV = int(fid / 16)  #int division.

        #DEBUG print("minecraft chunk texture x,y within image: %d,%d" % (mcTexU, mcTexV))
    
        #multiply by square size to get U1,V1:
    
        u1 = (mcTexU * 16.0) / 256.0    # or >> 4 (div by imagesize to get as fraction)
        v1 = (mcTexV * 16.0) / 256.0    # ..
    
        v1 = 1.0 - v1 #y goes low to high for some reason.
    
        #DEBUG print("That means u1,v1 is %f,%f" % (u1,v1))
    
        #16px will be 1/16th of the image.
        #The image is 256px wide and tall.

        uvUnit = 1/16.0

        mcUV1 = Vector((u1,v1))
        mcUV2 = Vector((u1+uvUnit,v1))
        mcUV3 = Vector((u1+uvUnit,v1-uvUnit))  #subtract uvunit for y  
        mcUV4 = Vector((u1, v1-uvUnit))

        #DEBUG print("Creating UVs for face with values: %f,%f to %f,%f" % (u1,v1,mcUV3[0], mcUV3[1]))

        #can we assume the cube faces are always the same order? It seems so, yes.
        #So,face 0 is the bottom.
        if fnum == 1:    # top
            face.uv1 = mcUV2
            face.uv2 = mcUV1
            face.uv3 = mcUV4
            face.uv4 = mcUV3
        elif fnum == 5:    #back
            face.uv1 = mcUV1
            face.uv2 = mcUV4
            face.uv3 = mcUV3
            face.uv4 = mcUV2
        else:   #bottom (0) and all the other sides..
            face.uv1 = mcUV3
            face.uv2 = mcUV2
            face.uv3 = mcUV1
            face.uv4 = mcUV4

    return "".join([blockname, 'UVs'])

    #References for UV stuff:

#http://www.blender.org/forum/viewtopic.php?t=15989&view=previous&sid=186e965799143f26f332f259edd004f4

    #newUVs = cubeMesh.uv_textures.new('lapisUVs')
    #newUVs.data.values() -> list... readonly?

    #contains one item per face...
    #each item is a bpy_struct MeshTextureFace
    #each has LOADS of options
    
    # .uv1 is a 2D Vector(u,v)
    #they go:
    
    # uv1 --> uv2
    #          |
    #          V
    # uv4 <-- uv3
    #
    # .. I think

## For comments/explanation, see above.
def createInsetUVs(blockname, me, matrl, faceIndices, insets):
    """Returns name of UV layer created."""
    __listtype = type([])
    if type(faceIndices) != __listtype:
        if (type(faceIndices) == type(0)):
            faceIndices = [faceIndices]*6
            print("Applying singular value to all 6 faces")
        else:
            print("setting material and uvs for %s: non-numerical face list" % blockname)
            print(faceIndices)
            raise IndexError("improper face assignment data!")

    #faceindices: array of minecraft material indices into the terrain.png.
    #Face order is [Bottom,Top,Right,Front,Left,Back]
    uname = blockname + 'UVs'
    blockUVLayer = me.uv_textures.new(uname)

    xim = getMCImg()
    #ADD THE MATERIAL! ...but why not earlier than this? uv layer add first?
    if matrl.name not in me.materials:
        me.materials.append(matrl)

    meshtexfaces = blockUVLayer.data.values()
    matrl.game_settings.alpha_blend = 'CLIP'
    matrl.game_settings.use_backface_culling = False
    
    #Insets are [bottom,top,sides]
    uvUnit = 1/16.0
    uvPixl = uvUnit / 16.0
    iB = insets[0] * uvPixl
    iT = insets[1] * uvPixl
    iS = insets[2] * uvPixl
    for fnum, fid in enumerate(faceIndices):
        face = meshtexfaces[fnum]
        face.image = xim
        #Pick UV square off the 2D texture surface based on its Minecraft index
        #eg 160 for lapis, 49 for glass... etc, makes for x,y:
        mcTexU = fid % 16
        mcTexV = int(fid / 16)  #int division.
        #DEBUG print("MC chunk tex x,y in image: %d,%d" % (mcTexU, mcTexV))
        #multiply by square size to get U1,V1:

        u1 = (mcTexU * 16.0) / 256.0    # or >> 4 (div by imagesize to get as fraction)
        v1 = (mcTexV * 16.0) / 256.0
        v1 = 1.0 - v1 #y goes low to high for some reason. (er...)
        #DEBUG print("That means u1,v1 is %f,%f" % (u1,v1))
    
        #16px will be 1/16th of the image.
        #The image is 256px wide and tall.

        mcUV1 = Vector((u1,v1))
        mcUV2 = Vector((u1+uvUnit,v1))
        mcUV3 = Vector((u1+uvUnit,v1-uvUnit))  #subtract uvunit for y  
        mcUV4 = Vector((u1, v1-uvUnit))

        #DEBUG print("Creating UVs for face with values: %f,%f to %f,%f" % (u1,v1,mcUV3[0], mcUV3[1]))

        #can we assume the cube faces are always the same order? It seems so, yes.
        #So, face 0 is the bottom.
        if fnum == 0:   #bottom
            face.uv1 = mcUV3
            face.uv2 = mcUV2
            face.uv3 = mcUV1
            face.uv4 = mcUV4

            face.uv3 = Vector((face.uv3[0]+iS, face.uv3[1]-iS))
            face.uv2 = Vector((face.uv2[0]-iS, face.uv2[1]-iS))
            face.uv1 = Vector((face.uv1[0]-iS, face.uv1[1]+iS))
            face.uv4 = Vector((face.uv4[0]+iS, face.uv4[1]+iS))
        
        elif fnum == 1:    # top
            face.uv1 = mcUV2
            face.uv2 = mcUV1
            face.uv3 = mcUV4
            face.uv4 = mcUV3
            
            #do insets! OMG, they really ARE anticlockwise. wtfbbq!
            #why wasn't it right the very, very first time?!?!
            ## Nope. This is fucked. The error is endemic and spread
            #through all uv application in this script.
            #vertex ordering isn't the problem, script references have
            #confused the entire issue.
    # uv1(2)-> uv2 (UV1)
    #          |
    #          V
    # uv4(3) <-- uv3(UV4)
            face.uv2 = Vector((face.uv2[0]+iS, face.uv2[1]-iS))
            face.uv1 = Vector((face.uv1[0]-iS, face.uv1[1]-iS))
            face.uv4 = Vector((face.uv4[0]-iS, face.uv4[1]+iS))
            face.uv3 = Vector((face.uv3[0]+iS, face.uv3[1]+iS))

        elif fnum == 5:    #back
            face.uv1 = mcUV1
            face.uv2 = mcUV4
            face.uv3 = mcUV3
            face.uv4 = mcUV2

            face.uv1 = Vector((face.uv1[0]+iS, face.uv1[1]-iT))
            face.uv4 = Vector((face.uv4[0]-iS, face.uv4[1]-iT))
            face.uv3 = Vector((face.uv3[0]-iS, face.uv3[1]+iB))
            face.uv2 = Vector((face.uv2[0]+iS, face.uv2[1]+iB))
            
        else:   #all the other sides..
            face.uv1 = mcUV3
            face.uv2 = mcUV2
            face.uv3 = mcUV1
            face.uv4 = mcUV4

            face.uv3 = Vector((face.uv3[0]+iS, face.uv3[1]-iT))
            face.uv2 = Vector((face.uv2[0]-iS, face.uv2[1]-iT))
            face.uv1 = Vector((face.uv1[0]-iS, face.uv1[1]+iB))
            face.uv4 = Vector((face.uv4[0]+iS, face.uv4[1]+iB))
        

    return "".join([blockname, 'UVs'])

#CYCLES! Exciting!

#for an emission, we just replace the diffuse node (Diffuse BDSF) with an Emission node (EMISSION)
# You can't just change the type as it's read-only, so will need to create a new node of the right type,
# put it in the old BSDF node's location, then swap the inputs and finally delete the old (disconnected)
#diffuse node.
# For transparency, need to script-in A'n'W's setup.

def createDiffuseCyclesMat(mat):
    """Changes a BI basic textured, diffuse material for use with Cycles.
    Assumes that the material in question already has an associated UV Mapping."""

    #Switch render engine to Cycles. Yippee ki-yay!
    if bpy.context.scene.render.engine != 'CYCLES':
        bpy.context.scene.render.engine = 'CYCLES'

    mat.use_nodes = True

    #maybe check number of nodes - there should be 2.
    ntree = mat.node_tree
    
    #print("Examining material nodetree for %s!" % mat.name)
    #print("["%s,%s" % (n.name, n.type) for n in mat.node_tree.nodes]")
    
    #get refs to existing nodes:
    diffNode = ntree.nodes['Diffuse BSDF']
    matOutNode = ntree.nodes['Material Output']
    #add the two new ones we need (texture inputs)
    imgTexNode = ntree.nodes.new(type='TEX_IMAGE')
    texCoordNode = ntree.nodes.new(type='TEX_COORD')

    #Plug the UVs from texCoord into the Image texture (and assign the image from existing texture!)
    #img = mat. texture? .image?
    imgTexNode.image = getMCImg() ##bpy.data.images['terrain.png']   #hardwired for MCraft...
    #maybe imgTexNode.color_space = 'LINEAR' needed?! probably yes...
    
    ntree.links.new(input=texCoordNode.outputs['UV'], output=imgTexNode.inputs['Vector'])

    #Plug the image output into the diffuseNode's Color input
    ntree.links.new(input=imgTexNode.outputs['Color'], output=diffNode.inputs['Color'])
    
    #Arrange the nodes in a clean layout:
    texCoordNode.location = Vector((-200, 200))
    imgTexNode.location = Vector((0, 200))
    diffNode.location = Vector((250,200))
    matOutNode.location = Vector((450,200))


def createEmissionCyclesMat(mat, emitAmt):
    """Changes a BI basic textured, diffuse material for use with Cycles.
    Sets up the same as a diffuse cycles material, but with emission instead of Diffuse BDSF.
    Assumes that the material in question already has an associated UV Mapping."""

    createDiffuseCyclesMat(mat)

    ntree = mat.node_tree   #there will now be 4 nodes in there, one of them being the diffuse shader.
    nodes = ntree.nodes
    links = ntree.links


    #get ref to existing nodes:
    diffNode = nodes['Diffuse BSDF']
    emitNode = nodes.new(type='EMISSION')

    #position emission node on same place as diff was:
    #loc = diffNode.location
    #emitNode.location = loc
    emitNode.location = diffNode.location

    #change links: delete the old links and add new ones.

    colorDiffSockIn = diffNode.inputs['Color']
    emitNode.inputs['Strength'].default_value = float(emitAmt) #set this from the EMIT value of data passed in.

    bsdfDiffSockOut = diffNode.outputs['BSDF']
    emitSockOut = emitNode.outputs[0]

    for nl in links:
        if nl.to_socket == colorDiffSockIn:
            links.remove(nl)

        if nl.from_socket == bsdfDiffSockOut:
            links.remove(nl)

    #now create new linkages to the new emit node:

    matOutNode = nodes['Material Output']
    imgTexNode = nodes['Image Texture']
    links.new(input=imgTexNode.outputs['Color'], output=emitNode.inputs['Color'])
    links.new(input=emitNode.outputs[0], output=matOutNode.inputs['Surface'])

    #and remove the diffuse shader, which is no longer needed.
    nodes.remove(diffNode)


def createPlainTransparentCyclesMat(mat):
    """Creates an 'alpha-transparent' Cycles material with no colour-cast overlay.
    Useful for objects such as Ladders, Doors, Flowers, Tracks, etc. """

    #Ensure Cycles is in use
    if bpy.context.scene.render.engine != 'CYCLES':
        bpy.context.scene.render.engine = 'CYCLES'
    mat.use_nodes = True

    ntree = mat.node_tree
    ntree.nodes.clear()

    #Create all needed nodes:
    nn = ntree.nodes.new(type="TEX_COORD")
    nn.name = "Texture Coordinate"
    nn.location = Vector((-200.000, 200.000))
    nn = ntree.nodes.new(type="OUTPUT_MATERIAL")
    nn.name = "Material Output"
    nn.location = Vector((850.366, 221.132))
    #nn.inputs['Displacement'].default_value = 0.0
    nn = ntree.nodes.new(type="TEX_IMAGE")
    nn.name = "Image Texture"
    nn.location = Vector((35.307, 172.256))
    #nn.inputs['Vector'].default_value = bpy.data.node_groups['Shader Nodetree'].nodes["Image Texture"].inputs[0].default_value
    nn.image = getCyclesMCImg()
    
    #todo: fix/set the image texture. This needs to be the scaled-up one, here. So make it the normal one, but with a different name.
    #check diffuse for how this gets set to the right value!
    nn = ntree.nodes.new(type="RGBTOBW")
    nn.name = "RGB to BW"
    nn.location = Vector((217.001, 274.182))

    nn = ntree.nodes.new(type="MATH")
    nn.name = "AlphaBlackGT"
    nn.operation = 'GREATER_THAN'
    nn.location = Vector((387.480, 325.267))
    nn.inputs[0].default_value = 0.001
    #nn.inputs[1].default_value = 0.001
    nn = ntree.nodes.new(type="BSDF_DIFFUSE")
    nn.name = "Diffuse BSDF"
    nn.location = Vector((357.214, 181.751))
    ###nn.inputs['Color'].default_value = bpy.data.node_groups['Shader Nodetree'].nodes["Diffuse BSDF"].inputs[0].default_value
    nn.inputs['Roughness'].default_value = 0.0
    nn = ntree.nodes.new(type="BSDF_TRANSPARENT")
    nn.name = "Transparent BSDF"
    nn.location = Vector((356.909, 70.560))
    ###nn.inputs['Color'].default_value = bpy.data.node_groups['Shader Nodetree'].nodes["Transparent BSDF"].inputs[0].default_value
    nn = ntree.nodes.new(type="MIX_SHADER")
    nn.name = "Mix Shader"
    nn.location = Vector((641.670, 223.397))
    nn.inputs['Fac'].default_value = 0.5

    #link creation
    nd = ntree.nodes
    links = ntree.links
    links.new(input=nd['Diffuse BSDF'].outputs['BSDF'], output=nd['Mix Shader'].inputs[1])
    links.new(input=nd['Texture Coordinate'].outputs['UV'], output=nd['Image Texture'].inputs['Vector'])
    links.new(input=nd['Image Texture'].outputs['Color'], output=nd['Diffuse BSDF'].inputs['Color'])
    links.new(input=nd['Image Texture'].outputs['Color'], output=nd['RGB to BW'].inputs['Color'])
    links.new(input=nd['Mix Shader'].outputs['Shader'], output=nd['Material Output'].inputs['Surface'])
    links.new(input=nd['Transparent BSDF'].outputs['BSDF'], output=nd['Mix Shader'].inputs[2])
    links.new(input=nd['AlphaBlackGT'].outputs['Value'], output=nd['Mix Shader'].inputs['Fac'])
    links.new(input=nd['RGB to BW'].outputs['Val'], output=nd['AlphaBlackGT'].inputs[1])    #2nd input. Tres importante.

    
    
def setupCyclesMat(material, cyclesParams):
    if 'emit' in cyclesParams:
        emitAmt = cyclesParams['emit']
        if emitAmt > 0.0:
            createEmissionCyclesMat(material, emitAmt)
            return

    if 'transp' in cyclesParams and cyclesParams['transp']: #must be boolean true
        if 'ovr' in cyclesParams:
            #get the overlay colour, and create a transp overlay material.
            return
        #not overlay
        createPlainTransparentCyclesMat(material)
        return
    
    createDiffuseCyclesMat(material)

    



def getMCMat(blocktype, rgbtriple, cyclesParams=None):  #take cycles params Dictionary - ['type': DIFF/EMIT/TRANSP, 'emitAmt': 0.0]
    """Creates or returns a general-use default Minecraft material."""
    matname = blocktype + 'Mat'

    if matname in bpy.data.materials:
        return bpy.data.materials[matname]


    blockMat = bpy.data.materials.new(matname)
    ## ALL-MATERIAL DEFAULTS
    blockMat.use_transparency = True # surely not for everything!? not stone,dirt,etc!
    blockMat.alpha = 0.0
    blockMat.specular_alpha = 0.0
    blockMat.specular_intensity = 0.0

    ##TODO: blockMat.use_transparent_shadows - on recving objects (solids)
    ##TODO: Cast transparent shadows from translucent things like water.
    if rgbtriple is not None:
        #create the solid shaded-view material colour
        diffusecolour = [n/256.0 for n in rgbtriple]
        blockMat.diffuse_color = diffusecolour
        blockMat.diffuse_shader = 'OREN_NAYAR'
        blockMat.diffuse_intensity = 0.8
        blockMat.roughness = 0.909
    else:
        #create a blank/obvious 'unhelpful' material.
        blockMat.diffuse_color = [214,127,255] #shocking pink
    return blockMat


def createInsetMCBlock(mcname, colourtriple, mcfaceindices, insets=[0,0,0], cyclesParams=None):
    """With no insets (the default), creates a full-size cube.
Else uses [bottom,top,sides] to inset the cube size and UV coords. Side insets are applied symmetrically around the model. Maximum side inset is 7.
Units are in Minecraft texels - so from 1 to 15. Inset 16 is an error."""
    blockname = mcname + 'Block'
    if blockname in bpy.data.objects:
        return bpy.data.objects[blockname]

    #Base cube
    bpy.ops.object.mode_set(mode='OBJECT')  #just to be sure... needed?
    bpy.ops.mesh.primitive_cube_add()
    blockOb = bpy.context.object    #ref to last created ob.
    bpy.ops.transform.resize(value=(0.5, 0.5, 0.5)) #quarter size (to 1x1x1)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    blockOb.name = blockname
    mesh = blockOb.data
    meshname = blockname + 'Mesh'
    mesh.name = meshname

    #Inset the mesh
    verts = mesh.vertices
    botface = mesh.faces[0]
    topface = mesh.faces[1]

#    sidefaces = mesh.faces[2:] [Bottom,Top,Right,Front,Left,Back]
    rgface = mesh.faces[2]
    frface = mesh.faces[3]
    leface = mesh.faces[4]
    bkface = mesh.faces[5]
    
    pxlUnit = 1/16.0
    bi = insets[0] * pxlUnit
    ti = insets[1] * pxlUnit
    si = insets[2] * pxlUnit

    #does this need to be enforced as global rather than local coords?
    #There are ways to inset these along their normal directions,
    #but it's complex to understand, so I'll just inset all sides. :(
    for v in topface.vertices:
        vtx = verts[v]
        vp = vtx.co
        vtx.co = Vector((vp[0], vp[1], vp[2]-ti))
    
    for v in botface.vertices:
        vtx = verts[v]
        vp = vtx.co
        vtx.co = Vector((vp[0], vp[1], vp[2]+bi))
    
    for v in rgface.vertices:
        vtx = verts[v]
        vp = vtx.co
        vtx.co = Vector((vp[0]-si, vp[1], vp[2]))

    for v in frface.vertices:
        vtx = verts[v]
        vp = vtx.co
        vtx.co = Vector((vp[0], vp[1]+si, vp[2]))

    for v in leface.vertices:
        vtx = verts[v]
        vp = vtx.co
        vtx.co = Vector((vp[0]+si, vp[1], vp[2]))

    for v in bkface.vertices:
        vtx = verts[v]
        vp = vtx.co
        vtx.co = Vector((vp[0], vp[1]-si, vp[2]))
        
    #Fetch/setup the material.
    blockMat = getMCMat(mcname, colourtriple, cyclesParams)
    
    mcTexture = getMCTex()
    blockMat.texture_slots.add()  #it has 18, but unassignable...
    mTex = blockMat.texture_slots[0]
    mTex.texture = mcTexture
    #set as active texture slot?
    
    mTex.texture_coords = 'UV'
    mTex.use_map_alpha = True	#mibbe not needed?

    mcuvs = createInsetUVs(mcname, mesh, blockMat, mcfaceindices, insets)

    if mcuvs is not None:
        mTex.uv_layer = mcuvs

    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.transform.rotate(value=(-1.5708,), axis=(0, 0, 1), constraint_axis=(False, False, True), constraint_orientation='GLOBAL')
    bpy.ops.mesh.select_all(action='DESELECT')
    bpy.ops.object.mode_set(mode='OBJECT')

    #last, setup cycles on the material if user asked for it.
    if cyclesParams is not None:
        setupCyclesMat(blockMat, cyclesParams)

    return blockOb


def createMCBlock(mcname, colourtriple, mcfaceindices, cyclesParams=None):
    """Creates a new minecraft WHOLE-block if it doesn't already exist, properly textured.
    Array order for mcfaceindices is: [bottom, top, right, front, left, back]"""

    #Has an instance of this blocktype already been made?
    blockname = mcname + 'Block'
    if blockname in bpy.data.objects:
        return bpy.data.objects[blockname]

    #Create cube
    bpy.ops.mesh.primitive_cube_add()
    blockOb = bpy.context.object    #get ref to last created ob.
    bpy.ops.transform.resize(value=(0.5, 0.5, 0.5))    #quarter size (to 1x1x1: it's currently 2x2x2 bu)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    blockOb.name = blockname
    blockMesh = blockOb.data
    meshname = blockname + 'Mesh'
    blockMesh.name = meshname

    #Fetch/setup the material.
    blockMat = getMCMat(mcname, colourtriple, cyclesParams)

#    #ADD THE MATERIAL! (conditional on it already being applied?)
#    blockMesh.materials.append(blockMat)    # previously is in the uvtex creation function for some reason...

    mcTexture = getMCTex()
    blockMat.texture_slots.add()  #it has 18, but unassignable...
    mTex = blockMat.texture_slots[0]
    mTex.texture = mcTexture
    #set as active texture slot?
    
    mTex.texture_coords = 'UV'
    mTex.use_map_alpha = True	#mibbe not needed?

    mcuvs = createBlockCubeUVs(mcname, blockMesh, blockMat, mcfaceindices)
    
    if mcuvs is not None:
        mTex.uv_layer = mcuvs
    #array order is: [bottom, top, right, front, left, back]
    
    #for the cube's faces to align correctly to Minecraft north, based on the UV assignments I've bodged, correct it all by spinning the verts after the fact. :p
    # -90degrees in Z. (clockwise a quarter turn)
    # Or, I could go through a crapload more UV assignment stuff, which is no fun at all.
    #bpy ENSURE MEDIAN rotation point, not 3d cursor pos.
    
    bpy.ops.object.mode_set(mode='EDIT')   ##the line below...
    #bpy.ops.objects.editmode_toggle()
    bpy.ops.mesh.select_all(action='SELECT')
    #don't want toggle! Want "ON"!
    bpy.ops.transform.rotate(value=(-1.5708,), axis=(0, 0, 1), constraint_axis=(False, False, True), constraint_orientation='GLOBAL')
    #bpy.ops.mesh.select_all(action='DESELECT')
    bpy.ops.object.mode_set(mode='OBJECT')

    #last, setup cycles on the material if user asked for it.
    if cyclesParams is not None:
        setupCyclesMat(blockMat, cyclesParams)

#    if cyclesparams is not None:
#        if 'emit' in cyclesparams:
#            emitAmt = cyclesparams['emit']
#            if emitAmt > 0.0:
#                createEmissionCyclesMat(blockMat, emitAmt)
#            else:
#                createDiffuseCyclesMat(blockMat)
#        else:
#            createDiffuseCyclesMat(blockMat)
    
    return blockOb

# #################################################


if __name__ == "__main__":
    #BlockBuilder.create ... might tidy up namespace.
    #nublock  = createMCBlock("Glass", (1,2,3), [49]*6)
    #nublock2 = createInsetMCBlock("Torch", (240,150,50), [80]*6, [0,6,7])
    
    nublock3 = createInsetMCBlock("Chest", (164,114,39), [25,25,26,27,26,26], [0,1,1])
    #print(nublock2.name)
