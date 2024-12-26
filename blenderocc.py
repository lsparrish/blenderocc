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
import json
from pathlib import Path
import inspect
import pkgutil
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
        
    def execute(self, operation, *shapes):
        try:
            result = getattr(self.get_module('BRepAlgoAPI'), f'BRepAlgoAPI_{operation}')(*shapes)
            result.Build()
            if result.IsDone():
                return result.Shape()
        except:
            return None

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
    def execute_operation(op_class, *args):
        try:
            module_name = op_class.__module__.split('.')[-1]
            exec(f"from OCC.Core import {module_name}")
            module = eval(module_name)
            
            operation = getattr(module, op_class.__name__)(*args)
            operation.Build()
            
            if operation.IsDone():
                return operation.Shape()
            return None
            
        except Exception as e:
            print(f"Operation failed: {str(e)}")
            return None

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


class OCCOperator(bpy.types.Operator):
    bl_idname = "occ.operator"
    bl_label = "OCC Operation"
    
    operation: bpy.props.StringProperty()
    preview_mode: bpy.props.BoolProperty(default=False)
    
    @classmethod 
    def poll(cls, context):
        if context.active_operator and hasattr(context.active_operator, 'operation'):
            return False
        if len(context.selected_objects) != 2:
            return False
        return all(o.type == 'MESH' for o in context.selected_objects)
        
    def execute(self, context):
        props = context.scene.occ_props
        obj1, obj2 = context.selected_objects
        try:
            wrapper = OCCWrapper()
            shape1 = wrapper.get_shape(obj1)
            shape2 = wrapper.get_shape(obj2)
            
            ops = {
                'UNION': 'Fuse',
                'DIFFERENCE': 'Cut', 
                'INTERSECTION': 'Common'
            }
            
            result_shape = wrapper.execute(ops[props.boolean_type], shape1, shape2)
            if result_shape:
                name = "Preview" if self.preview_mode else f"Boolean_{props.boolean_type}"
                result_mesh = wrapper.create_mesh(result_shape, name)
                
                if self.preview_mode:
                    if "Boolean_Preview" in bpy.data.objects:
                        prev_obj = bpy.data.objects["Boolean_Preview"]
                        prev_obj.data = result_mesh
                    else:
                        prev_obj = bpy.data.objects.new("Boolean_Preview", result_mesh)
                        context.scene.collection.objects.link(prev_obj)
                        prev_obj.display_type = 'WIRE'
                else:
                    result_obj = bpy.data.objects.new(result_mesh.name, result_mesh)
                    context.scene.collection.objects.link(result_obj)
                    
                    if "Boolean_Preview" in bpy.data.objects:
                        bpy.data.objects.remove(bpy.data.objects["Boolean_Preview"], do_unlink=True)
                    
                    for obj in (obj1, obj2):
                        bpy.data.objects.remove(obj, do_unlink=True)
                        
                return {'FINISHED'}
                    
        except Exception as e:
            self.report({'ERROR'}, f"Boolean operation failed: {str(e)}")
            return {'CANCELLED'}

class OCCSVGOperator(bpy.types.Operator):
    bl_idname = "occ.svg"
    bl_label = "Export SVG"
    
    @classmethod
    def poll(cls, context):
        return context.active_object and context.active_object.type == 'MESH'
        
    def execute(self, context):
        obj = context.active_object
        mesh = obj.data.copy()
        mesh.transform(obj.matrix_world)
        
        def iso_project(v):
            x,y,z = v.co
            a, b = 0.866025, 0.5
            return (x * a - y * a, x * b + y * b - z)
        
        points = [iso_project(v) for v in mesh.vertices]
        bounds = {'x': [p[0] for p in points], 'y': [p[1] for p in points]}
        margin = max(max(b) - min(b) for b in bounds.values()) * 0.1
        
        svg = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{min(bounds["x"])-margin} {min(bounds["y"])-margin} {max(bounds["x"])-min(bounds["x"])+2*margin} {max(bounds["y"])-min(bounds["y"])+2*margin}">']
        
        for face in sorted(mesh.polygons, key=lambda f: f.normal.z):
            path = [f"{points[i][0]},{points[i][1]}" for i in face.vertices]
            color = ["#808080","#a0a0a0","#d0d0d0"][int((face.normal.z+1)*1.499)]
            svg.append(f'<path d="M {path[0]} L {" L ".join(path[1:])} Z" fill="{color}" stroke="none"/>')
        
        svg.append('</svg>')
        context.window_manager.clipboard = '\n'.join(svg)
        bpy.data.meshes.remove(mesh)
        self.report({'INFO'}, "SVG copied to clipboard")
            
        return {'FINISHED'}

class OCCCustomOperator(bpy.types.Operator):
    bl_idname = "occ.custom"
    bl_label = "Execute Custom"
    
    operation: bpy.props.StringProperty()
    
    def execute(self, context):
        text_name = "Custom Operations"
        if text_name not in bpy.data.texts:
            self.report({'ERROR'}, "Click Edit Code first")
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
    
    def execute(self, context):
        text_name = "Custom Operations"
        if text_name not in bpy.data.texts:
            bpy.data.texts.new(text_name)
            
        bpy.ops.screen.area_dupli('INVOKE_DEFAULT')
        area = context.window_manager.windows[-1].screen.areas[0]
        area.type = 'TEXT_EDITOR'
        area.spaces[0].text = bpy.data.texts[text_name]
        return {'FINISHED'}

class VIEW3D_PT_OCCTools(bpy.types.Panel):
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "OCC Tools"
    bl_label = "CAD Operations"

    def draw(self, context):
        layout = self.layout
        props = context.scene.occ_props
        
        box = layout.box()
        box.label(text="Export")
        box.operator("occ.svg", text="Copy SVG")
        
        box = layout.box()
        box.label(text="Boolean Operations")
        
        if len(context.selected_objects) == 2:
            obj1, obj2 = context.selected_objects
            box.label(text=f"Target: {obj1.name}")
            box.label(text=f"Tool: {obj2.name}")
            box.operator("occ.operator", text="Preview", icon='HIDE_OFF').preview_mode = True
        else:
            box.label(text="Select two mesh objects", icon='INFO')
            
        box.prop(props, "boolean_type")
        row = box.row()
        op = row.operator("occ.operator", text="Execute Boolean", icon='PLAY')
        op.operation = 'BOOLEAN'
        op.preview_mode = False

class VIEW3D_PT_OCCCustom(bpy.types.Panel):
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "OCC Tools"
    bl_label = "Custom Code"
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        return True

    def draw(self, context):
        layout = self.layout
        box = layout.box()
        
        row = box.row()
        row.operator("occ.edit_code", text="Edit Code", icon='TEXT')
        row.operator("occ.custom", text="Execute Code", icon='PLAY')
        
        text_name = "Custom Operations"
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

class OCCProperties(bpy.types.PropertyGroup):
    boolean_type: bpy.props.EnumProperty(
        name="Operation",
        items=[('UNION', "Union", "Combine objects"),
               ('DIFFERENCE', "Difference", "Subtract second object"),
               ('INTERSECTION', "Intersection", "Keep overlap")],
        default='UNION'
    )

classes = [
    OCCProperties,
    OCCOperator,
    OCCSVGOperator,
    OCCCustomOperator,
    OCCEditOperator,
    VIEW3D_PT_OCCTools,
    VIEW3D_PT_OCCCustom
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.occ_props = bpy.props.PointerProperty(type=OCCProperties)

def unregister():
    del bpy.types.Scene.occ_props
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
