
from indu_doc.god import God
from indu_doc.xtarget import XTarget, XTargetType
from indu_doc.attributes import Attribute, AttributeType, get_attribute_type
from indu_doc.connection import Pin, Link, Connection

from enum import Enum
from peewee import *


def get_db(db_file):
    return SqliteDatabase(db_file)

class BaseModel(Model):
    class Meta:
        database = None 


class EnumField(Field):
    field_type = 'text'

    def __init__(self, enum_type: type[Enum], *args, **kwargs):
        self.enum_type = enum_type
        super().__init__(*args, **kwargs)

    def db_value(self, value):
        if value is None:
            return None
        if isinstance(value, self.enum_type):
            return value.value
        raise ValueError(f"Expected {self.enum_type}, got {type(value)}")

    def python_value(self, value):
        if value is None:
            return None
        return self.enum_type(value)
    

# class JSONField(Field):
#     field_type = 'text'

#     def __init__(self, enum_type: type[Enum], *args, **kwargs):
#         self.enum_type = enum_type
#         super().__init__(*args, **kwargs)

#     def db_value(self, value):
#         if value is None:
#             return None
#         if isinstance(value, self.enum_type):
#             return value.value
#         raise ValueError(f"Expected {self.enum_type}, got {type(value)}")

#     def python_value(self, value):
#         if value is None:
#             return None
#         return self.enum_type(value)


# db models
class SettingsModel(BaseModel):
    key= CharField(primary_key=True)
    value = TextField()


class XTargetModel(BaseModel):
    guid = CharField(primary_key=True) 
    target_type = EnumField(XTargetType)


class AspectModel(BaseModel):
    guid = CharField(primary_key=True) 
    separator = CharField()
    value = CharField() 

    sort_order = IntegerField() 

    parent = ForeignKeyField(XTargetModel, backref='aspects')


class ConnectionModel(BaseModel):
    guid = CharField(primary_key=True) 
    
    src = ForeignKeyField(XTargetModel, backref='out_connections', null=True)
    dst = ForeignKeyField(XTargetModel, backref='in_connections', null=True)
    through = ForeignKeyField(XTargetModel, backref='through_connections', null=True)


class LinkModel(BaseModel):
    guid = CharField(primary_key=True) 
    name = CharField()
    # src_pin_name ? dst_pin_name ?

    parent = ForeignKeyField(ConnectionModel, backref='links')
    from_pin = ForeignKeyField('Pin', backref='out_link', null=True)
    to_pin = ForeignKeyField('Pin', backref='in_link', null=True)


class PinModel(BaseModel):
    id = CharField(primary_key=True) 
    name = CharField()
    role = CharField(3)

    parent = ForeignKeyField(Link, backref='pins', null=True)  # parent link


class AttributeModel(BaseModel):
    id = CharField(primary_key=True) 
    name = CharField()
    value = TextField()
    type = EnumField(AttributeType)

    xtarget = ForeignKeyField(XTargetModel, backref='attributes', null=True)
    pin = ForeignKeyField(PinModel, backref='attributes', null=True)
    link = ForeignKeyField(LinkModel, backref='attributes', null=True)
    aspect = ForeignKeyField(AspectModel, backref='attributes', null=True)
    
# TODO
class DocumentModel(BaseModel):
    mime = CharField()
    file = BlobField()

class PageModel(BaseModel):
    number = IntegerField()
    link = ForeignKeyField(DocumentModel, backref='pages')


# main functions
def save_to_db(god: God, filename: str):
    db = get_db(filename)
    db.connect()
    db.create_tables([
        XTargetModel, 
        AspectModel, 
        AttributeModel, 
        PinModel, 
        LinkModel, 
        ConnectionModel, 
        SettingsModel,
        ])
    
    # go through all models to make insertion dicts
    # xtargets
    xtarget_insert_data = []
    for guid, xtarget in god.xtargets.items():
        xtarget_insert_data.append({
            "guid": guid,
            "type": xtarget.target_type
        })
    with db.atomic():
        XTargetModel.bulk_create(xtarget_insert_data, batch_size=100)

    # aspects
    aspect_insert_data = []
    for guid, aspect in god.aspects.items():
        aspect_insert_data.append({
            "guid": guid,
            "separator": aspect.separator,
            "value": aspect.value,
        })
    with db.atomic():
        AspectModel.bulk_create(aspect_insert_data, batch_size=100)

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
        ConnectionModel.bulk_create(aspect_insert_data, batch_size=100)

    # links (create without pins)
    link_insert_data = []
    for guid, link in god.links.items():
        link_insert_data.append({
            "guid": guid,
            "name": link.name,
            "parent": link.parent.get_guid(),  # assumes ConnectionModel already exists
            "from_pin": None,
            "to_pin": None
        })
    with db.atomic():
        LinkModel.bulk_create(link_insert_data, batch_size=100)

    # pins
    pin_insert_data = []
    for guid, pin in god.pins.items():
        pin_insert_data.append({
            "guid": guid,
            "name": pin.name,
            "role": pin.role,
            "parent": link.parent.get_guid(), 
        })
    with db.atomic():
        PinModel.bulk_create(pin_insert_data, batch_size=100)

    # attach pins to links
    with db.atomic():
        for guid, link in god.links.items():
            LinkModel.update(
                from_pin=link.src_pin.get_guid() if link.src_pin else None,
                to_pin=link.dest_pin.get_guid() if link.dest_pin else None
            ).where(LinkModel.guid == guid).execute()

    # attributes
    attr_insert_data = []
    for _, attr in god.attributes.items():
        attr_insert_data.append({
            "id": attr.get_guid(),
            "name": attr.name,
            "value": attr.get_db_representation(),
            "type": get_attribute_type(attr.__class__).value
        })   
    with db.atomic():
        AttributeModel.bulk_create(attr_insert_data, batch_size=100)


def load_from_db(god: God, filename: str):
    pass



