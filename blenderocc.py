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

class OCCCustomOperator(bpy.types.Operator):
    bl_idname = "occ.custom"
    bl_label = "Execute Custom"
    
    operation: bpy.props.StringProperty()
    
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
    
    TEXT_NAME = "custom_commands.py"
    
    @staticmethod
    def get_template_path():
        """Get the path to the project directory using PWD environment variable"""
        return os.environ['PWD']
    
    def create_text_if_needed(self):
        """Create text data block if needed"""
        if self.TEXT_NAME not in bpy.data.texts:
            text = bpy.data.texts.new(self.TEXT_NAME)
            template_path = self.get_template_path()
            with open(os.path.join(template_path, self.TEXT_NAME), 'r') as f:
                template_content = f.read()
            if template_content:
                text.write(template_content)
        return bpy.data.texts[self.TEXT_NAME]
    
    def create_text_editor(self, context):
        """Create new text editor area"""
        bpy.ops.screen.area_dupli('INVOKE_DEFAULT')
        window = context.window_manager.windows[-1]
        area = window.screen.areas[0]
        area.type = 'TEXT_EDITOR'
        return area
    
    def execute(self, context):
        text = self.create_text_if_needed()
        area = self.create_text_editor(context)
        area.spaces[0].text = text
        return {'FINISHED'}

class VIEW3D_PT_OCCTools(bpy.types.Panel):
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "OCC Tools"
    bl_label = "CAD Operations"

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
                        op = box.operator("occ.custom", text=func.op_name)
                        op.operation = name
            except:
                pass

classes = [
    OCCCustomOperator,
    OCCEditOperator,
    VIEW3D_PT_OCCTools
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
