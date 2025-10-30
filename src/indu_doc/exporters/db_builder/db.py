from __future__ import annotations
import os
import logging
import mimetypes
from typing import Any, Callable

from peewee import DeferredForeignKey, Model, SqliteDatabase
from indu_doc.god import God, PagesObjectsMapper
from indu_doc.xtarget import XTarget, XTargetType
from indu_doc.attributes import Attribute, AttributeType, get_attribute_type
from enum import Enum
from peewee import CharField, IntegerField, ForeignKeyField, BlobField
from playhouse.sqlite_ext import JSONField

logger = logging.getLogger(__name__)

def get_mime_type(file_path: str, file_blob: bytes) -> str:
    """
    Get MIME type of a file using Python's mimetypes module.
    
    Args:
        file_path: Path to the file
        file_blob: Binary content of the file (unused, kept for compatibility)
    
    Returns:
        MIME type string
    """
    mime_type, _ = mimetypes.guess_type(file_path)
    return mime_type or 'application/octet-stream'

def get_db(db_file):
    return SqliteDatabase(db_file)


def batch_insert(model, data, batch_size=100):
    """
    Insert data in batches to avoid SQLite variable limit (999 variables).
    
    Args:
        model: The Peewee model to insert into
        data: List of dictionaries to insert
        batch_size: Number of records per batch (default 100)
    """
    if not data:
        return
    
    # Calculate safe batch size based on number of fields
    # SQLite has a limit of 999 variables, so we need to ensure:
    # batch_size * num_fields < 999
    if data:
        num_fields = len(data[0])
        safe_batch_size = min(batch_size, 999 // num_fields - 1)
        if safe_batch_size < 1:
            safe_batch_size = 1
    else:
        safe_batch_size = batch_size
    
    for i in range(0, len(data), safe_batch_size):
        batch = data[i:i + safe_batch_size]
        model.insert_many(batch).execute()


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
def save_to_db(god: God, db_file: str = ':memory:') -> str:
    """
    Save a God instance to a SQLite database.
    
    Args:
        god: The God instance to save
        db_file: Path to the database file, or ':memory:' for in-memory database
        
    Returns:
        The database file path or ':memory:'
    """
    db = get_db(db_file)
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
    if xtarget_insert_data:
        with db.atomic():
            batch_insert(XTargetModel, xtarget_insert_data)

    # aspects
    aspect_insert_data = []
    for guid, aspect in god.aspects.items():
        aspect_insert_data.append({
            "guid": guid,
            "separator": aspect.separator,
            "value": aspect.value,
        })
    if aspect_insert_data:
        with db.atomic():
            batch_insert(AspectModel, aspect_insert_data)

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

    if xtarget_aspect_through_insert_data:
        with db.atomic():
            batch_insert(XTargetAspectThroughModel, xtarget_aspect_through_insert_data)

    # connections
    connection_insert_data = []
    for guid, connection in god.connections.items():
        connection_insert_data.append({
            "guid": guid,
            "src": connection.src.get_guid() if connection.src else None,
            "dst": connection.dest.get_guid() if connection.dest else None,
            "through": connection.through.get_guid() if connection.through else None,
        })
    if connection_insert_data:
        with db.atomic():
            batch_insert(ConnectionModel, connection_insert_data)

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
    if link_insert_data:
        with db.atomic():
            batch_insert(LinkModel, link_insert_data)

    # pins - now god.pins contains all pins including child pins
    pin_insert_data = []
    for guid, pin in god.pins.items():
        pin_insert_data.append({
            "guid": guid,
            "name": pin.name,
            "role": pin.role,
            "parentLink": pin.parentLink.get_guid() if pin.parentLink else None
        })
    if pin_insert_data:
        with db.atomic():
            batch_insert(PinModel, pin_insert_data)
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
    if attr_insert_data:
        with db.atomic():
            batch_insert(AttributeModel, attr_insert_data)

    
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
    if attributed_obj_attr_through_insert_data:
        with db.atomic():
            batch_insert(AttributedObjAttributeThroughModel, attributed_obj_attr_through_insert_data)

    # page_mapper
    pm: PagesObjectsMapper = god.pages_mapper
    
    # Validate that all paths in the mapper are absolute before saving
    for file_path in pm.file_paths:
        if not os.path.isabs(file_path):
            logger.error(f"Non-absolute path found in mapper before save: {file_path}")
            raise ValueError(f"PageMapper contains non-absolute path: {file_path}. All paths must be absolute.")
    
    documents_insert_data = []
    
    # first gather unique documents to insert
    for file_p in pm.file_paths:
        # get blob data from the path
        with open(file_p, 'rb') as f:
            file_blob = f.read()
        file_name = os.path.basename(os.path.abspath(file_p))
        documents_insert_data.append({
            "fileName": file_name,
            "mime": get_mime_type(file_p, file_blob),
            "file": file_blob
        })
    
    if documents_insert_data:
        with db.atomic():
            batch_insert(DocumentModel, documents_insert_data)
        
    # now insert pages
    page_insert_data = []

    for page_entry in pm.page_to_objects.keys():
        document = DocumentModel.get(DocumentModel.fileName == os.path.basename(os.path.abspath(page_entry.file_path)))
        page_insert_data.append({
            "number": page_entry.page_number,
            "document": document.id
        })
    
    if page_insert_data:
        with db.atomic():
            batch_insert(PageModel, page_insert_data)
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
    
    if page_object_through_insert_data:
        with db.atomic():
            batch_insert(PageObjectThroughModel, page_object_through_insert_data)
    
    # save configs into metadata
    meta_insert_data = {
        "configs": god.configs.get_db_representation()
    }
    MetaDataModel.create(**meta_insert_data)
    
    db.close()
    return db_file

def extract_documents_from_db(db_filename: str, output_dir: str) -> dict[str, str]:
    """
    Extract all document blobs from the database and save them to the output directory.
    
    Args:
        db_filename: Path to the database file
        output_dir: Directory where documents will be saved
        
    Returns:
        A dictionary mapping original filenames to their new absolute paths
    """
    db = get_db(db_filename)
    db.bind([DocumentModel])
    
    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)
    
    filename_to_path = {}
    documents = DocumentModel.select()
    
    for doc in documents:
        # Create the full output path
        output_path = os.path.join(output_dir, doc.fileName)
        
        # Write the blob to disk
        with open(output_path, 'wb') as f:
            f.write(doc.file)
        
        # Store the mapping
        filename_to_path[doc.fileName] = os.path.abspath(output_path)
    
    db.close()
    return filename_to_path


def load_from_db(filename: str, extract_docs_to: str) -> God:
    """
    Load a God instance from a database file.
    
    Args:
        filename: Path to the database file
        extract_docs_to: Directory path where document blobs will be extracted.
                        Documents must be saved to disk to obtain absolute paths for the mapper.
    
    Returns:
        A God instance reconstructed from the database
    """
    from indu_doc.configs import AspectsConfig
    from indu_doc.attributes import AvailableAttributes
    from indu_doc.connection import Connection, Link, Pin
    from indu_doc.tag import Tag, Aspect
    from indu_doc.god import PageMapperEntry
    
    # Extract documents (required to get absolute paths)
    filename_to_path = extract_documents_from_db(filename, extract_docs_to)
    
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
        # Use _id suffix to access foreign key ID without triggering database query
        parent_guid = link_model.parent_id
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
        # Use _id suffix to access foreign key ID without triggering database query
        child_pin = None
        child_pin_id = pin_model.childPin_id
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
        
        # Use _id suffix to access foreign key IDs without triggering database queries
        src_pin_id = link_model.src_pin_id
        if src_pin_id:
            src_pin = build_pin(src_pin_id, link)
            if src_pin:
                link.set_src_pin(src_pin)
        
        dest_pin_id = link_model.dest_pin_id
        if dest_pin_id:
            dest_pin = build_pin(dest_pin_id, link)
            if dest_pin:
                link.set_dest_pin(dest_pin)
    
    # Step 7: Reconstruct the PagesObjectsMapper
    # Build a mapping of document ID to filename
    document_models = DocumentModel.select()
    doc_id_to_filename = {doc.id: doc.fileName for doc in document_models}
    
    page_models = PageModel.select()
    for page_model in page_models:
        # Use _id suffix to access foreign key ID without triggering database query
        document_id = page_model.document_id
        document_filename = doc_id_to_filename.get(document_id)
        
        if not document_filename:
            continue
        
        # Get the absolute path from extracted documents
        # PageMapper should ONLY contain absolute paths, never just filenames
        if document_filename not in filename_to_path:
            # Document wasn't extracted - skip this page entry
            logger.warning(f"Document {document_filename} not found in extracted files, skipping page {page_model.number}")
            continue
            
        # Ensure the path is absolute (it should already be from extract_documents_from_db)
        file_path = os.path.abspath(filename_to_path[document_filename])
        
        # Add the absolute file path to the tracked file paths
        god.pages_mapper._file_paths.add(file_path)
        
        page_entry = PageMapperEntry(
            page_number=page_model.number,
            file_path=file_path
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



