bl_info = {
    "name": "OpenCASCADE Tools",
    "author": "Luke Parrish",
    "version": (1, 0, 1),
    "blender": (4, 3, 2),
    "location": "View3D > N-Panel > OCC Tools",
    "category": "Object",
}

import bpy
import numpy as np
import os
from functools import wraps

def occ_operation(name):
    def decorator(func):
        @wraps(func)
        def wrapper(wrapper_instance, *args, **kwargs):
            return func(wrapper_instance, *args, **kwargs)
        wrapper.is_occ_op = True
        wrapper.op_name = name
        return wrapper
    return decorator

class OCCWrapper:
    def __init__(self):
        self.oc = {}
        
    def get_module(self, name):
        if name not in self.oc:
            self.oc[name] = OCCUtils.import_occ(name)[name]
        return self.oc[name]
        
    def get_shape(self, obj):
        return OCCUtils.create_solid(obj)
        
    def create_mesh(self, shape, name="OCCResult"):
        return OCCUtils.shape_to_mesh(shape, name)
        
    def create_object(self, method, args=None, kwargs=None, name=None):
        args = args or []
        kwargs = kwargs or {}
        
        module, cls = method.split('.')
        shape = getattr(self.get_module(module), cls)(*args, **kwargs).Shape()
        
        if name:
            mesh = self.create_mesh(shape, name)
            obj = bpy.data.objects.new(name, mesh)
            bpy.context.scene.collection.objects.link(obj)
            return obj
        return shape
    text_name='custom_commands.py'
    def switch_to_text(text_name='custom_commands.py'):
        return OCCUtils.switch_to_text(text_name)

class OCCUtils:
    @staticmethod
    def import_occ(*modules):
        results = {}
        for module in modules:
            try:
                exec(f"from OCC.Core import {module}")
                results[module] = eval(module)
            except ImportError as e:
                raise ImportError(f"Failed to import {module}: {e}")
        return results

    @staticmethod
    def mesh_to_points(obj):
        mesh = obj.data.copy()
        verts = np.array([v.co for v in mesh.vertices])
        matrix = np.array(obj.matrix_world)
        verts = np.c_[verts, np.ones(len(verts))] @ matrix.T
        verts = verts[:, :3]
        bpy.data.meshes.remove(mesh)
        return verts

    @staticmethod
    def create_solid(obj):
        oc = OCCUtils.import_occ('BRep', 'gp', 'TopoDS', 'BRepBuilderAPI', 'TopAbs')
        verts = OCCUtils.mesh_to_points(obj)
    
        compound = oc['TopoDS'].TopoDS_Compound()
        builder = oc['BRep'].BRep_Builder()
        builder.MakeCompound(compound)
    
        for poly in obj.data.polygons:
            points = [oc['gp'].gp_Pnt(*verts[idx]) for idx in poly.vertices]
            wire = oc['BRepBuilderAPI'].BRepBuilderAPI_MakeWire()

            for i in range(len(points)):
                edge = oc['BRepBuilderAPI'].BRepBuilderAPI_MakeEdge(points[i], points[(i + 1) % len(points)]).Edge()
                wire.Add(edge)
            
            if wire.IsDone():
                face = oc['BRepBuilderAPI'].BRepBuilderAPI_MakeFace(wire.Wire()).Face()
                builder.Add(compound, face)
    
        sewing = oc['BRepBuilderAPI'].BRepBuilderAPI_Sewing(1e-6)
        sewing.Add(compound)
        sewing.Perform()
        
        solid = oc['BRepBuilderAPI'].BRepBuilderAPI_MakeSolid()
        solid.Add(oc['TopoDS'].topods.Shell(sewing.SewedShape()))
        result = solid.Solid()
        
        return result

    @staticmethod
    def shape_to_mesh(shape, name="OCCMesh"):
        oc = OCCUtils.import_occ('BRepMesh', 'TopAbs', 'TopLoc', 'TopExp', 'TopoDS', 'BRep')
        mesh = bpy.data.meshes.new(name)
        verts, faces = [], []
        
        oc['BRepMesh'].BRepMesh_IncrementalMesh(shape, 0.1)
        explorer = oc['TopExp'].TopExp_Explorer(shape, oc['TopAbs'].TopAbs_FACE)
        
        while explorer.More():
            face = oc['TopoDS'].topods.Face(explorer.Current())
            loc = oc['TopLoc'].TopLoc_Location()
            tri = oc['BRep'].BRep_Tool.Triangulation(face, loc)
            
            if tri:
                offset = len(verts)
                transform = loc.Transformation()
                verts.extend((tri.Node(i).Transformed(transform).Coord()) for i in range(1, tri.NbNodes() + 1))
                
                forward = face.Orientation() == oc['TopAbs'].TopAbs_FORWARD
                for i in range(1, tri.NbTriangles() + 1):
                    n1, n2, n3 = tri.Triangle(i).Get()
                    faces.append((offset + n1 - 1, offset + (n2 if forward else n3) - 1, offset + (n3 if forward else n2) - 1))
            explorer.Next()
            
        mesh.from_pydata(verts, [], faces)
        mesh.update()
        return mesh

    @staticmethod
    def switch_to_text(text_name):
        """Helper function to switch to a text in the text editor"""
        def switch():
            for area in bpy.context.screen.areas:
                if area.type == 'TEXT_EDITOR':
                    for space in area.spaces:
                        if space.type == 'TEXT_EDITOR':
                            space.text = bpy.data.texts[text_name]
        bpy.app.timers.register(switch, first_interval=0.01)

class OCCCustomOperator(bpy.types.Operator):
    bl_idname = "occ.custom"
    bl_label = "Execute Custom"
    message: bpy.props.StringProperty(default="")
    operation: bpy.props.StringProperty()
    @classmethod
    def description(cls, context, properties):
        """Show docstring of the operation as a tooltip"""
        if properties.operation:
            text = bpy.data.texts.get("custom_commands.py")
            if text:
                try:
                    loc = {}
                    exec(text.as_string(), globals(), loc)
                    if properties.operation in loc:
                        return loc[properties.operation].__doc__ or "No description available"
                except:
                    pass
        return "Execute custom OpenCASCADE operation"
    def execute(self, context):
        text_name = "custom_commands.py"
        if text_name not in bpy.data.texts:
            self.report({'ERROR'}, "Click Custom Code first")
            return {'CANCELLED'}
            
        text = bpy.data.texts[text_name]
        code = text.as_string()
        
        try:
            wrapper = OCCWrapper()
            loc = {'wrapper': wrapper}
            exec(code, globals(), loc)
            
            if self.operation:
                if self.operation in loc:
                    op_func = loc[self.operation]
                    if hasattr(op_func, 'is_occ_op'):
                        result_shape = op_func(wrapper)
                        if result_shape:
                            mesh = wrapper.create_mesh(result_shape, f"{self.operation}_Result") 
                            obj = bpy.data.objects.new(mesh.name, mesh)
                            context.scene.collection.objects.link(obj)
                            return {'FINISHED'}
            elif 'result_shape' in loc:
                mesh = wrapper.create_mesh(loc['result_shape'], "Custom_Result")
                obj = bpy.data.objects.new(mesh.name, mesh)
                context.scene.collection.objects.link(obj)
                return {'FINISHED'}
                
        except Exception as e:
            self.report({'ERROR'}, f"Custom operation failed: {str(e)}")
            
        return {'CANCELLED'}

class OCCEditOperator(bpy.types.Operator):
    bl_idname = "occ.edit_code"
    bl_label = "Edit Code"
    
    text_name = "custom_commands.py"
    save_only: bpy.props.BoolProperty(default=False)
    
    @staticmethod
    def get_template_path():
        return os.environ['PWD']
    
    def create_text_if_needed(self):
        if self.text_name not in bpy.data.texts:
            text = bpy.data.texts.new(self.text_name)
            template_path = self.get_template_path()
            with open(os.path.join(template_path, self.text_name), 'r') as f:
                template_content = f.read()
            if template_content:
                text.write(template_content)
        return self.text_name

    def create_text_workspace(self, context):
        def setup_workspace():
            bpy.context.window_manager.windows[0].workspace = bpy.data.workspaces['Layout']
            new_ws = bpy.context.workspace
            new_ws.name = 'OCC Text'
            screen = new_ws.screens[0]
            screen.rename('OCC Text')
            for area in screen.areas:
                if area.type == 'VIEW_3D':
                    area.ui_type = 'TEXT_EDITOR'
                    for space in area.spaces:
                        if space.type == 'TEXT_EDITOR':
                            space.text = bpy.data.texts[OCCEditOperator.text_name]
            return None

        def duplicate_workspace():
            bpy.ops.workspace.duplicate()
            bpy.app.timers.register(setup_workspace, first_interval=0.01)
            return None

        if "OCC Text" not in bpy.data.workspaces:
            bpy.app.timers.register(duplicate_workspace, first_interval=0.01)
        return True
 
    def save_text_as_file(self, context):
        """Save current text to a file"""
        for area in context.screen.areas:
            if area.type == 'TEXT_EDITOR':
                text = area.spaces[0].text
                if text:
                    filepath = os.path.join(self.get_template_path(), text.name)
                    with open(filepath, 'w') as f:
                        f.write(text.as_string())
                    self.report({'INFO'}, f"Saved to {filepath}")
                    return {'FINISHED'}
        return {'CANCELLED'}

    def execute(self, context):
        if self.save_only:
            return self.save_text_as_file(context)
        text_name = self.create_text_if_needed()
        OCCUtils.switch_to_text(text_name)
        if "OCC Text" in bpy.data.workspaces:
            context.window.workspace = bpy.data.workspaces["OCC Text"]
            if context.window.workspace == bpy.data.workspaces.get("OCC Text"):
                return self.save_text_as_file(context)
            return {'FINISHED'}
        if self.create_text_workspace(context):
            return {'FINISHED'}
        return {'CANCELLED'}

class TextSwitchOperator(bpy.types.Operator):
    bl_idname = "text.switch"
    bl_label = "Switch Text"
    text_name: bpy.props.StringProperty()
    @classmethod
    def poll(cls, context):
        return (context.area.type == 'TEXT_EDITOR' 
                and len(bpy.data.texts) > 0 
                and context.space_data.text)
    def execute(self, context):
        current = context.space_data.text
        texts = list(bpy.data.texts)
        if not texts:
            return {'CANCELLED'}
        idx = texts.index(current) if current in texts else -1
        next_text = texts[(idx + 1) % len(texts)]
        
        # Split the area vertically and switch text
        override = context.copy()
        override['area'] = context.area
        bpy.ops.screen.area_split(override, direction='VERTICAL', factor=0.5)
        OCCUtils.switch_to_text(next_text.name)
        return {'FINISHED'}

class VIEW3D_PT_OCCTools(bpy.types.Panel):
    bl_idname = "VIEW3D_PT_OCCTools"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "OCC Tools"
    bl_label = "BlenderOCC Operations"

    def draw(self, context):
        layout = self.layout

        box = layout.box()
        row = box.row()
        row.operator("occ.edit_code", text="Custom Code", icon='TEXT')
        text_name = "custom_commands.py"
        if text_name in bpy.data.texts:
            text = bpy.data.texts[text_name]
            code = text.as_string()

            try:
                loc = {}
                exec(code, globals(), loc)
                for name, func in loc.items():
                    if hasattr(func, 'is_occ_op'):
                        if name == 'call_ai':
                            submenu = layout.column()
                            submenu.popover(panel="TEXT_PT_ai_panel", text=func.op_name)
                        else:
                            op = layout.operator("occ.custom", text=func.op_name)
                            op.operation = name
            except Exception as e:
                layout.label(text=f"Error: {str(e)}")

class TEXT_MT_occ_menu(bpy.types.Menu):
    bl_idname = "TEXT_MT_occ_menu"
    bl_label = "BlenderOCC"
    
    def draw(self, context):
        layout = self.layout
        layout.operator("occ.edit_code", text="Custom Code", icon='TEXT')
        layout.operator("occ.edit_code", text="Save To File", icon='FILE_TICK').save_only = True
        layout.separator()
        layout.menu("TEXT_MT_occ_switch_menu", text="Switch Text")
        text = bpy.data.texts.get("custom_commands.py")
        if text:
            try:
                code = text.as_string()
                wrapper = OCCWrapper()
                loc = {'wrapper': wrapper}
                exec(code, globals(), loc)
                for name, func in loc.items():
                    if hasattr(func, 'is_occ_op'):
                        if name == 'call_ai':
                            submenu = layout.column()
                            submenu.popover(panel="TEXT_PT_ai_panel", text=func.op_name)
                        else:
                            op = layout.operator("occ.custom", text=func.op_name)
                            op.operation = name
            except Exception as e:
                layout.label(text=f"Error: {str(e)}")

class TEXT_PT_ai_panel(bpy.types.Panel):
    bl_label = "AI Message"
    bl_space_type = 'TEXT_EDITOR'
    bl_region_type = 'UI'
    bl_options = {'INSTANCED'}

    def draw(self, context):
        layout = self.layout
        layout.prop(context.scene, "ai_message", text="")
        op = layout.operator("occ.custom", text="Send")
        op.operation = "call_ai"

class TEXT_MT_occ_switch_menu(bpy.types.Menu):
    bl_idname = "TEXT_MT_occ_switch_menu"
    bl_label = "Switch Text"
    
    def draw(self, context):
        layout = self.layout
        for text in bpy.data.texts:
            op = layout.operator("text.switch", text=text.name)
            op.text_name = text.name

class TextSwitchOperator(bpy.types.Operator):
    bl_idname = "text.switch"
    bl_label = "Switch Text"
    text_name: bpy.props.StringProperty()
    
    def execute(self, context):
        OCCUtils.switch_to_text(self.text_name)
        return {'FINISHED'}

classes = [
    OCCCustomOperator,
    OCCEditOperator,
    VIEW3D_PT_OCCTools,
    TEXT_MT_occ_menu,
    TEXT_MT_occ_switch_menu,
    TEXT_PT_ai_panel,
    TextSwitchOperator
]

addon_keymaps = []

def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.ai_message = bpy.props.StringProperty(
        name="AI Message",
        description="Enter your question or request for the AI assistant",
        default="",
        options={'TEXTEDIT_UPDATE'}
    )
    def draw_occ_menu(self, context):
        self.layout.menu("TEXT_MT_occ_menu")
    global menu_func
    menu_func = draw_occ_menu
    bpy.types.TEXT_MT_editor_menus.append(menu_func)
    wm = bpy.context.window_manager
    kc = wm.keyconfigs.addon
    if kc:
        km = kc.keymaps.new(name='Text', space_type='TEXT_EDITOR')
        kmi = km.keymap_items.new(TextSwitchOperator.bl_idname, type='RIGHT_BRACKET', value='PRESS', ctrl=True)
        addon_keymaps.append((km, kmi))
    

def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    del bpy.types.Scene.ai_message
    bpy.types.TEXT_MT_editor_menus.remove(menu_func)
    for km, kmi in addon_keymaps:
        km.keymap_items.remove(kmi)
    addon
