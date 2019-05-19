import bmesh
import operator
from mathutils import Vector
from bmesh.types import BMVert

from ..rails import CreateRailing
from ...utils import split, split_quad, filter_geom


def create_stairs(bm, faces, prop):
    """Extrude steps from selected faces

    Args:
        bm (TYPE): Description
        faces (TYPE): Description
        prop (TYPE): Description
    """

    for f in faces:
        f.select = False

        f = create_stair_split(bm, f, prop.size_offset)

        _key = operator.attrgetter("co.z")
        fheight = max(f.verts, key=_key).co.z - min(f.verts, key=_key).co.z

        # -- options for railing
        top_faces = []
        init_normal = f.normal.copy()

        ext_face = f
        for i in range(prop.step_count):
            # extrude face
            n = ext_face.normal
            ext_width = (
                prop.landing_width if (prop.landing and i == 0) else prop.step_width
            )
            ret_face = bmesh.ops.extrude_discrete_faces(bm, faces=[ext_face]).get(
                "faces"
            )[-1]

            bmesh.ops.translate(bm, vec=n * ext_width, verts=ret_face.verts)

            # -- keep reference to top faces for railing
            top_faces.append(
                list(
                    {f for e in ret_face.edges for f in e.link_faces if f.normal.z > 0}
                )[-1]
            )

            if prop.landing and i == 0:
                # adjust ret_face based on stair direction

                left_normal, right_normal = (
                    ret_face.normal.cross(Vector((0, 0, 1))),
                    ret_face.normal.cross(Vector((0, 0, -1))),
                )
                left = list(
                    {
                        f
                        for e in ret_face.edges
                        for f in e.link_faces
                        if f.normal.to_tuple(4) == left_normal.to_tuple(4)
                    }
                )[-1]
                right = list(
                    {
                        f
                        for e in ret_face.edges
                        for f in e.link_faces
                        if f.normal.to_tuple(4) == right_normal.to_tuple(4)
                    }
                )[-1]

                # set appropriate face for next extrusion
                if prop.stair_direction == "FRONT":
                    pass
                elif prop.stair_direction == "LEFT":
                    ret_face = left
                elif prop.stair_direction == "RIGHT":
                    ret_face = right

            if i < (prop.step_count - 1):
                # cut step height
                res = split_quad(bm, ret_face, False, 1)
                bmesh.ops.translate(
                    bm,
                    verts=filter_geom(res["geom_inner"], BMVert),
                    vec=(0, 0, (fheight / 2) - (fheight / (prop.step_count - i))),
                )

                # update ext_face
                ext_face = min(
                    [f for f in filter_geom(res["geom_inner"], BMVert)[-1].link_faces],
                    key=lambda f: f.calc_center_median().z,
                )

    if prop.railing:
        create_stairs_railing(bm, init_normal, top_faces, prop)


def create_stair_split(bm, face, prop):
    """Use properties from SplitOffset to subdivide face into regular quads

    Args:
        bm (bmesh.types.BMesh): bmesh for current edit mesh
        face (bmesh.types.BMFace): face to make split (must be quad)
        prop (TYPE): Description

    Returns:
        bmesh.types.BMFace: New face created after split
    """
    size, off = prop.size, prop.offset
    return split(bm, face, size.y, size.x, off.x, off.y, off.z)


def create_stairs_railing(bm, normal, faces, prop):
    """Create railing for stairs

    Args:
        bm (TYPE): Description
        normal (Vector3): Normal direction for initial face of stairs
        faces (list): top faces of the stairs
        prop (TYPE): Description
    """

    # -- create railing for landing
    if prop.landing:
        landing_face, *step_faces = faces

        if prop.stair_direction == "FRONT":
            create_railing_front(bm, landing_face, normal, prop.rail)
        elif prop.stair_direction == "LEFT":
            create_railing_left(bm, landing_face, normal, prop.rail)
        elif prop.stair_direction == "RIGHT":
            create_railing_right(bm, landing_face, normal, prop.rail)

    else:
        step_faces = faces

    # --create railing for steps
    create_step_railing(bm, normal, step_faces, prop)


def create_railing_front(bm, face, normal, prop):
    """Create rails for landing when stair direction is front

    Args:
        bm (bmesh.types.BMesh): bmesh of current edit object
        face (bmesh.types.BMFace): Top face of the landing
        normal (Vector3): Normal direction for the initial face of stairs
        prop (TYPE): Description
    """

    # -- determine left and right edges
    valid_edges = []
    valid_loops = [l for l in face.loops]
    for e in face.edges:
        for loop in e.link_loops:
            if loop in valid_loops:
                tan = e.calc_tangent(loop)
                if round(normal.cross(tan).z):
                    valid_edges.append(e)

    CreateRailing().from_edges(bm, valid_edges, prop)


def create_railing_left(bm, face, normal, prop):
    """Create rails for landing when stair direction is left

    Args:
        bm (bmesh.types.BMesh): bmesh of current edit object
        face (bmesh.types.BMFace): Top face of the landing
        normal (Vector3): Normal direction for the initial face of stairs
        prop: extra kwargs from StairProperty
    """

    # -- determine front and left edges
    valid_edges = []
    valid_loops = [l for l in face.loops]
    for e in face.edges:
        for loop in e.link_loops:
            if loop in valid_loops:
                tan = e.calc_tangent(loop)
                if tan == -normal:
                    valid_edges.append(e)

                if round(normal.cross(tan).z) < 0:
                    valid_edges.append(e)

    CreateRailing().from_edges(bm, valid_edges, prop)


def create_railing_right(bm, face, normal, prop):
    """Create rails for landing when stair direction is right

    Args:
        bm (bmesh.types.BMesh): bmesh of current edit object
        face (bmesh.types.BMFace): Top face of the landing
        normal (Vector3): Normal direction for the initial face of stairs
        prop: extra kwargs from StairProperty
    """

    # -- determine front and right edges
    valid_edges = []
    valid_loops = [l for l in face.loops]
    for e in face.edges:
        for loop in e.link_loops:
            if loop in valid_loops:
                tan = e.calc_tangent(loop)
                if tan == -normal:
                    valid_edges.append(e)

                if round(normal.cross(tan).z) > 0:
                    valid_edges.append(e)

    CreateRailing().from_edges(bm, valid_edges, prop)


def create_step_railing(bm, normal, faces, prop):
    """Create railing for stair steps

    Args:
        bm (bmesh.types.BMesh): current editmode bmesh
        normal (Vector): Normal direction for the initial face of stairs
        faces (bmesh.types.BMFace): Top faces for stairs
        prop (TYPE): Description
    """

    # -- update normal based on stair direction
    if prop.stair_direction == "LEFT":
        normal = normal.cross(Vector((0, 0, 1)))
    elif prop.stair_direction == "RIGHT":
        normal = normal.cross(Vector((0, 0, -1)))

    # -- get all left and right edges
    left_edges = []
    right_edges = []

    for face in faces:
        for edge in face.edges:
            for loop in edge.link_loops:
                if loop in [l for l in face.loops]:
                    tan = edge.calc_tangent(loop)

                    if round(normal.cross(tan).z) < 0:
                        right_edges.append(edge)

                    if round(normal.cross(tan).z) > 0:
                        left_edges.append(edge)

    # -- filter edges based on direction
    valid_edges = []
    if prop.stair_direction == "FRONT":
        valid_edges.extend(left_edges + right_edges)
    elif prop.stair_direction == "LEFT":
        valid_edges.extend(right_edges)
    elif prop.stair_direction == "RIGHT":
        valid_edges.extend(left_edges)

    # CreateRailing().from_step_edges(
    #     bm, valid_edges, normal, prop.stair_direction, prop.rail
    # )
