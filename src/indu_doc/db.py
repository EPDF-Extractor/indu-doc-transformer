from __future__ import annotations
import os
from typing import Any, Callable
import magic

from peewee import DeferredForeignKey, Model, SqliteDatabase
from indu_doc.god import God, PagesObjectsMapper
from indu_doc.xtarget import XTarget, XTargetType
from indu_doc.attributes import Attribute, AttributeType, get_attribute_type
from enum import Enum
from peewee import CharField, IntegerField, ForeignKeyField, BlobField
from playhouse.sqlite_ext import JSONField

def get_db(db_file):
    return SqliteDatabase(db_file)

class BaseModel(Model):
    class Meta:
        pass


class EnumField(CharField):
    """
    This class enable an Enum like field for Peewee
    """

    def __init__(self, choices: Callable, *args: Any, **kwargs: Any) -> None:
        super(CharField, self).__init__(*args, **kwargs)
        self.choices = choices
        self.max_length = 255

    def db_value(self, value: Any) -> Any:
        return value.value

    def python_value(self, value: Any) -> Any:
        return self.choices(type(list(self.choices)[0].value)(value))

# db models
class XTargetModel(BaseModel):
    guid = CharField(primary_key=True)
    tag = CharField(max_length=512)
    target_type = EnumField(XTargetType)

    
class AspectModel(BaseModel):
    guid = CharField(primary_key=True) 
    separator = CharField()
    value = CharField() 

class XTargetAspectThroughModel(BaseModel):
    xtarget = ForeignKeyField(XTargetModel, backref='aspect_throughs')
    aspect = ForeignKeyField(AspectModel, backref='xtarget_throughs')
    sort_order = IntegerField() 

class ConnectionModel(BaseModel):
    guid = CharField(primary_key=True)
    src = ForeignKeyField(XTargetModel, backref='out_connections', null=True)
    dst = ForeignKeyField(XTargetModel, backref='in_connections', null=True)
    through = ForeignKeyField(XTargetModel, backref='through_connections', null=True)


class LinkModel(BaseModel):
    guid = CharField(primary_key=True) 
    name = CharField() # full name
    parent = ForeignKeyField(ConnectionModel, backref='links')
    src_pin = DeferredForeignKey('PinModel', backref='out_link', null=True)
    dest_pin = DeferredForeignKey('PinModel', backref='in_link', null=True)
    src_pin_name = CharField(null=True) 
    dest_pin_name = CharField(null=True)


class PinModel(BaseModel):
    guid = CharField(primary_key=True) 
    name = CharField()
    role = CharField(3)
    childPin = ForeignKeyField('self', backref='parent_pin', null=True)
    parentLink = ForeignKeyField(LinkModel, backref='pins', null=True)  # parent link

class AttributeModel(BaseModel):
    id = CharField(primary_key=True) 
    name = CharField()
    value = JSONField()
    type = EnumField(AttributeType)
    
class ALL_ATTRIBUTED_MODELS(Enum):
    XTARGET = 'xtarget'
    PIN = 'pin'
    LINK = 'link'
    ASPECT = 'aspect'
class AttributedObjAttributeThroughModel(BaseModel):
    attributed_obj_type = EnumField(ALL_ATTRIBUTED_MODELS)
    attributed_obj_id = CharField()  # guid or id of the attributed object
    attribute = ForeignKeyField(AttributeModel, backref='attributed_obj_throughs')


# TODO
class DocumentModel(BaseModel):
    fileName = CharField()
    mime = CharField()
    file = BlobField()

class PageModel(BaseModel):
    number = IntegerField()
    document = ForeignKeyField(DocumentModel, backref='pages')


class PageObjectThroughModel(BaseModel):
    page = ForeignKeyField(PageModel, backref='object_throughs')
    object_type = CharField()  # e.g., 'xtarget', 'pin', 'link', 'aspect'
    object_id = CharField()  # guid or id of the object


class MetaDataModel(BaseModel):
    configs = JSONField()

# main functions
def save_to_db(god: God, filename: str):
    db = get_db(filename)
    all_models = [
        XTargetModel,
        AspectModel,
        AttributeModel,
        PinModel,
        LinkModel, 
        ConnectionModel, 
        AttributedObjAttributeThroughModel,
        PageObjectThroughModel,
        XTargetAspectThroughModel,
        DocumentModel,
        PageModel,
        MetaDataModel
        ]
    db.bind(all_models)
    db.connect()
    # clear existing tables, if any
    db.drop_tables(all_models)
    # create tables
    db.create_tables(all_models)
    
    # go through all models to make insertion dicts
    
    # xtargets
    xtarget_insert_data = []
    for guid, xtarget in god.xtargets.items():
        xtarget_insert_data.append({
            "guid": guid,
            "target_type": xtarget.target_type,
            "tag": str(xtarget.tag.tag_str)
        })
    with db.atomic():
        XTargetModel.insert_many(xtarget_insert_data).execute()

    # aspects
    aspect_insert_data = []
    for guid, aspect in god.aspects.items():
        aspect_insert_data.append({
            "guid": guid,
            "separator": aspect.separator,
            "value": aspect.value,
        })
    with db.atomic():
        AspectModel.insert_many(aspect_insert_data).execute()

    # xtarget-aspect through
    xtarget_aspect_through_insert_data = []
    for guid, xtarget in god.xtargets.items():
        tag_asps = xtarget.tag.get_aspects()
        if not tag_asps:
            continue
        sort_order = 0
        for (_, level_aspects) in tag_asps.items():
            for aspect in level_aspects:
                xtarget_aspect_through_insert_data.append({
                    "xtarget": guid,
                    "aspect": aspect.get_guid(),
                    "sort_order": sort_order
                })
                sort_order += 1


    with db.atomic():
        XTargetAspectThroughModel.insert_many(xtarget_aspect_through_insert_data).execute()

    # connections
    connection_insert_data = []
    for guid, connection in god.connections.items():
        connection_insert_data.append({
            "guid": guid,
            "src": connection.src.get_guid() if connection.src else None,
            "dst": connection.dest.get_guid() if connection.dest else None,
            "through": connection.through.get_guid() if connection.through else None,
        })
    with db.atomic():
        ConnectionModel.insert_many(connection_insert_data).execute()

    # links (create without pins, filled later)
    link_insert_data = []
    for guid, link in god.links.items():
        link_insert_data.append({
            "guid": guid,
            "name": link.name,
            "parent": link.parent.get_guid(),  # assumes ConnectionModel already exists
            "src_pin": None,
            "dest_pin": None,
            "src_pin_name": link.src_pin_name if hasattr(link, 'src_pin_name') else None,
            "dest_pin_name": link.dest_pin_name if hasattr(link, 'dest_pin_name') else None
        })
    with db.atomic():
        LinkModel.insert_many(link_insert_data).execute()

    # pins - now god.pins contains all pins including child pins
    pin_insert_data = []
    for guid, pin in god.pins.items():
        pin_insert_data.append({
            "guid": guid,
            "name": pin.name,
            "role": pin.role,
            "parentLink": pin.parentLink.get_guid() if pin.parentLink else None
        })
    with db.atomic():
        PinModel.insert_many(pin_insert_data).execute()
    # attach childPin
    with db.atomic():
        for guid, pin in god.pins.items():
            PinModel.update(
                childPin=pin.child.get_guid() if pin.child else None,
            ).where(PinModel.guid == guid).execute()

    # attach pins to links
    with db.atomic():
        for guid, link in god.links.items():
            LinkModel.update(
                src_pin=link.src_pin.get_guid() if link.src_pin else None,
                dest_pin=link.dest_pin.get_guid() if link.dest_pin else None,
                src_pin_name=link.src_pin_name if hasattr(link, 'src_pin_name') else None,
                dest_pin_name=link.dest_pin_name if hasattr(link, 'dest_pin_name') else None
            ).where(LinkModel.guid == guid).execute()
            

    # attributes
    attr_insert_data = []
    for _, attr in god.attributes.items():
        attr_insert_data.append({
            "id": attr.get_guid(),
            "name": attr.name,
            "value": attr.get_db_representation(),
            "type": get_attribute_type(attr.__class__)
        })   
    with db.atomic():
        AttributeModel.insert_many(attr_insert_data).execute()

    
    # attributed obj - attribute through
    attributed_obj_attr_through_insert_data = []
    # we need to insert for xtargets, pins, links, aspects
    for xtarget in god.xtargets.values():
        for attr in xtarget.attributes:
            attributed_obj_attr_through_insert_data.append({
                "attributed_obj_type": ALL_ATTRIBUTED_MODELS.XTARGET,
                "attributed_obj_id": xtarget.get_guid(),
                "attribute": attr.get_guid()
            })
    # god.pins now contains all pins including child pins
    for pin in god.pins.values():
        for attr in pin.attributes:
            attributed_obj_attr_through_insert_data.append({
                "attributed_obj_type": ALL_ATTRIBUTED_MODELS.PIN,
                "attributed_obj_id": pin.get_guid(),
                "attribute": attr.get_guid()
            })
    for link in god.links.values():
        for attr in link.attributes:
            attributed_obj_attr_through_insert_data.append({
                "attributed_obj_type": ALL_ATTRIBUTED_MODELS.LINK,
                "attributed_obj_id": link.get_guid(),
                "attribute": attr.get_guid()
            })
    for aspect in god.aspects.values():
        for attr in aspect.attributes:
            attributed_obj_attr_through_insert_data.append({
                "attributed_obj_type": ALL_ATTRIBUTED_MODELS.ASPECT,
                "attributed_obj_id": aspect.get_guid(),
                "attribute": attr.get_guid()
            })
    with db.atomic():
        AttributedObjAttributeThroughModel.insert_many(attributed_obj_attr_through_insert_data).execute()

    # page_mapper
    pm: PagesObjectsMapper = god.pages_mapper
    documents_seen_set = set()
    documents_insert_data = []
    
    # first gather unique documents to insert
    for page_entry in pm.page_to_objects.keys():
        if page_entry.file_path not in documents_seen_set:
            documents_seen_set.add(page_entry.file_path)
            # get blob data from the path
            with open(page_entry.file_path, 'rb') as f:
                file_blob = f.read()
            file_name = os.path.basename(os.path.abspath(page_entry.file_path))
            documents_insert_data.append({
                "fileName": file_name,
                "mime": magic.from_buffer(file_blob, mime=True),
                "file": file_blob
            })
    with db.atomic():
        DocumentModel.insert_many(documents_insert_data).execute()
        
    # now insert pages
    page_insert_data = []

    for page_entry in pm.page_to_objects.keys():
        document = DocumentModel.get(DocumentModel.fileName == os.path.basename(os.path.abspath(page_entry.file_path)))
        page_insert_data.append({
            "number": page_entry.page_number,
            "document": document.id
        })
        
    with db.atomic():
        PageModel.insert_many(page_insert_data).execute()
    # now insert page-object throughs
    page_object_through_insert_data = []
    for page_entry, objects in pm.page_to_objects.items():
        page = PageModel.get(
            (PageModel.number == page_entry.page_number) & 
            (PageModel.document == DocumentModel.get(DocumentModel.fileName == os.path.basename(os.path.abspath(page_entry.file_path))).id)
        )
        for obj in objects:
            # Skip objects without get_guid (like PageError)
            if not hasattr(obj, 'get_guid') or not callable(getattr(obj, 'get_guid', None)):
                continue
            page_object_through_insert_data.append({
                "page": page.id,
                "object_type": obj.__class__.__name__.lower(),
                "object_id": getattr(obj, 'get_guid')()  # type: ignore
            })
        
    with db.atomic():
        PageObjectThroughModel.insert_many(page_object_through_insert_data).execute()    
    
    # save configs into metadata
    meta_insert_data = {
        "configs": god.configs.get_db_representation()
    }
    MetaDataModel.create(**meta_insert_data)
    
    db.close()


def load_from_db(filename: str) -> God:
    from indu_doc.configs import AspectsConfig
    from indu_doc.attributes import AvailableAttributes
    from indu_doc.connection import Connection, Link, Pin
    from indu_doc.tag import Tag, Aspect
    from indu_doc.god import PageMapperEntry
    
    db = get_db(filename)
    all_models = [
        XTargetModel,
        AspectModel,
        AttributeModel,
        PinModel,
        LinkModel, 
        ConnectionModel, 
        AttributedObjAttributeThroughModel,
        PageObjectThroughModel,
        XTargetAspectThroughModel,
        DocumentModel,
        PageModel,
        MetaDataModel
    ]
    db.bind(all_models)
    db.connect()
    
    # Load metadata (configs)
    metadata = MetaDataModel.get()
    configs = AspectsConfig.init_from_list(metadata.configs)
    
    # Initialize God instance
    god = God(configs)
    
    # Step 1: Load all attributes first (they are referenced by other objects)
    attr_models = AttributeModel.select()
    for attr_model in attr_models:
        attr_type = attr_model.type
        attr_class = AvailableAttributes[attr_type]
        attr_instance = attr_class.from_db_representation(attr_model.value)
        god.attributes[attr_model.id] = attr_instance
    
    # Helper function to get attributes for an object
    def get_attributes_for_object(obj_type: ALL_ATTRIBUTED_MODELS, obj_id: str) -> list[Attribute]:
        throughs = AttributedObjAttributeThroughModel.select().where(
            (AttributedObjAttributeThroughModel.attributed_obj_type == obj_type) &
            (AttributedObjAttributeThroughModel.attributed_obj_id == obj_id)
        )
        attrs = []
        for through in throughs:
            attr_id = through.attribute.id
            if attr_id in god.attributes:
                attrs.append(god.attributes[attr_id])
        return attrs
    
    # Step 2: Load all aspects
    aspect_models = AspectModel.select()
    for aspect_model in aspect_models:
        attrs = get_attributes_for_object(ALL_ATTRIBUTED_MODELS.ASPECT, aspect_model.guid)
        aspect = Aspect(
            separator=aspect_model.separator,
            value=aspect_model.value,
            attributes=attrs
        )
        god.aspects[aspect_model.guid] = aspect
    
    # Step 3: Load all tags and XTargets
    xtarget_models = XTargetModel.select()
    for xtarget_model in xtarget_models:
        # Reconstruct the tag
        tag = Tag(xtarget_model.tag, configs)
        
        # Get aspects for this xtarget
        aspect_throughs = XTargetAspectThroughModel.select().where(
            XTargetAspectThroughModel.xtarget == xtarget_model.guid
        ).order_by(XTargetAspectThroughModel.sort_order)
        
        # Build aspects dict for the tag
        aspects_dict = {}
        for through in aspect_throughs:
            aspect_guid = through.aspect.guid
            if aspect_guid in god.aspects:
                aspect = god.aspects[aspect_guid]
                sep = aspect.separator
                if sep not in aspects_dict:
                    aspects_dict[sep] = []
                aspects_dict[sep].append(aspect)
        
        # Convert lists to tuples
        for sep in aspects_dict:
            aspects_dict[sep] = tuple(aspects_dict[sep])
        
        tag.set_aspects(aspects_dict)
        
        # Cache the tag
        god.tags[tag.tag_str] = tag
        
        # Create XTarget
        attrs = get_attributes_for_object(ALL_ATTRIBUTED_MODELS.XTARGET, xtarget_model.guid)
        xtarget = XTarget(
            tag=tag,
            configs=configs,
            target_type=xtarget_model.target_type,
            attributes=attrs
        )
        god.xtargets[xtarget_model.guid] = xtarget
    
    # Step 4: Load all connections (without links first)
    connection_models = ConnectionModel.select()
    for conn_model in connection_models:
        src = god.xtargets.get(conn_model.src.guid) if conn_model.src else None
        dst = god.xtargets.get(conn_model.dst.guid) if conn_model.dst else None
        through = god.xtargets.get(conn_model.through.guid) if conn_model.through else None
        
        connection = Connection(
            src=src,
            dest=dst,
            through=through,
            links=[]
        )
        god.connections[conn_model.guid] = connection
    
    # Step 5: Load all links (without pins first)
    link_models = LinkModel.select()
    
    for link_model in link_models:
        # Use __data__ to avoid database queries for foreign keys
        parent_guid = link_model.__data__.get('parent')
        parent_conn = god.connections.get(parent_guid)
        if not parent_conn:
            continue
        
        attrs = get_attributes_for_object(ALL_ATTRIBUTED_MODELS.LINK, link_model.guid)
        
        # Get pin names directly from the database
        src_pin_name = link_model.src_pin_name or ""
        dest_pin_name = link_model.dest_pin_name or ""
        
        link = Link(
            name=link_model.name,
            parent=parent_conn,
            src_pin_name=src_pin_name,
            dest_pin_name=dest_pin_name,
            attributes=attrs
        )
        god.links[link_model.guid] = link
        parent_conn.add_link(link)
    
    # Step 6: Load all pins recursively
    pin_models = {pm.guid: pm for pm in PinModel.select()}
    
    def build_pin(pin_guid: str, parent_link: Link) -> Pin | None:
        if pin_guid in god.pins:
            return god.pins[pin_guid]
        
        pin_model = pin_models.get(pin_guid)
        if not pin_model:
            return None
        
        # Build child pin first if it exists
        # Use __data__ to avoid triggering a database query
        child_pin = None
        child_pin_id = pin_model.__data__.get('childPin')
        if child_pin_id:
            child_pin = build_pin(child_pin_id, parent_link)
        
        attrs = get_attributes_for_object(ALL_ATTRIBUTED_MODELS.PIN, pin_guid)
        pin = Pin(
            name=pin_model.name,
            role=pin_model.role,
            parentLink=parent_link,
            attributes=attrs,
            child=child_pin
        )
        god.pins[pin_guid] = pin
        return pin
    
    # Now attach pins to links
    for link_model in link_models:
        link = god.links.get(link_model.guid)
        if not link:
            continue
        
        # Use __data__ to avoid triggering database queries
        src_pin_id = link_model.__data__.get('src_pin')
        if src_pin_id:
            src_pin = build_pin(src_pin_id, link)
            if src_pin:
                link.set_src_pin(src_pin)
        
        dest_pin_id = link_model.__data__.get('dest_pin')
        if dest_pin_id:
            dest_pin = build_pin(dest_pin_id, link)
            if dest_pin:
                link.set_dest_pin(dest_pin)
    
    # Step 7: Reconstruct the PagesObjectsMapper
    page_models = PageModel.select()
    for page_model in page_models:
        document = page_model.document
        page_entry = PageMapperEntry(
            page_number=page_model.number,
            file_path=document.fileName
        )
        
        # Get all objects on this page
        page_object_throughs = PageObjectThroughModel.select().where(
            PageObjectThroughModel.page == page_model.id
        )
        
        for through in page_object_throughs:
            obj_type = through.object_type
            obj_id = through.object_id
            
            # Find the object in the appropriate dictionary
            obj = None
            if obj_type == 'xtarget':
                obj = god.xtargets.get(obj_id)
            elif obj_type == 'connection':
                obj = god.connections.get(obj_id)
            elif obj_type == 'link':
                obj = god.links.get(obj_id)
            # Note: PageError objects are not reconstructed as they are runtime errors
            
            if obj:
                god.pages_mapper.page_to_objects[page_entry].add(obj)
                god.pages_mapper.object_to_pages[obj].add(page_entry)
    
    db.close()
    return god



