# -*- coding: utf-8 -*-
from enum import Flag, auto
from qgis.core import QgsVectorLayer

__author__ = 'malik@blesius.com'
__date__ = '2021-05-02'
__copyright__ = 'Copyright 2021, Malik Blesius'


BOOLEAN_FIELDS = {"bool", "boolean"}
DATE_FIELDS = {"date", "datetime"}
TIME_FIELDS = {"time", "timestamp", "timestamp without time zone"}
DATETIME_FIELDS = DATE_FIELDS | TIME_FIELDS
INTEGER_FIELDS = {"integer", "integer64", "int", "int4",
                  "uint", "longlong", "ulonglong"}
DECIMAL_FIELDS = {"double", "real", "decimal", "numeric"}
NUMERIC_FIELDS = INTEGER_FIELDS | DECIMAL_FIELDS
STRING_FIELDS = {"char", "string", "text", "varchar",
                 "nchar", "nvarchar"}
FIELD_TYPES = BOOLEAN_FIELDS | DATETIME_FIELDS | NUMERIC_FIELDS | STRING_FIELDS


class FieldTypes(Flag):
    INTEGER = auto()
    DECIMAL = auto()
    STRING = auto()
    DATE = auto()
    TIME = auto()
    BOOLEAN = auto()
    DATETIME = DATE | TIME
    NUMERIC = DECIMAL | INTEGER
    SUPPORTED_TYPES = BOOLEAN | STRING | DATETIME | NUMERIC
    UNSUPPORTED = None


def get_sort_key(field_type: FieldTypes) -> type:
    """ Based on the field type of the active field, the key for sorting
        the values (alphabetically, alphanumerically) is returned
    """
    if field_type == FieldTypes.DECIMAL:
        return float
    elif field_type == FieldTypes.INTEGER:
        return int
    else:
        return None


def is_expression_field(layer, field_name) -> bool:
    """ Returns true if a field is an expression/virtual field, otherwise
        return false.
        When the expression string is not empty and type name is empty.

    @param layer: The vector layer containing the field that should be checked
    @type layer: QgsVectorLayer
    @param field_name: Name of the field that should be checked
    @type field_name: String
    """

    field_names = layer.fields().names()
    if field_name not in set(field_names):
        raise NameError(f"{field_name} does not correspond to a field of the layer '{layer.name()}'")

    idx = layer.fields().indexFromName(field_name)
    field = layer.fields().at(idx)

    empty_expr_str = layer.expressionField(idx).__eq__('')
    empty_type_name = field.typeName().__eq__('')

    if not empty_expr_str and empty_type_name:
        return True
    else:
        return False


def match_field_type(field_type: str) -> FieldTypes:
    """ Matches field type to correct enum type
    @param field_type: Named field type"""
    if field_type.lower() in INTEGER_FIELDS:
        return FieldTypes.INTEGER
    elif field_type.lower() in DECIMAL_FIELDS:
        return FieldTypes.DECIMAL
    elif field_type.lower() in STRING_FIELDS:
        return FieldTypes.STRING
    elif field_type.lower() in DATE_FIELDS:
        return FieldTypes.DATE
    elif field_type.lower() in TIME_FIELDS:
        return FieldTypes.TIME
    elif field_type.lower() in BOOLEAN_FIELDS:
        return FieldTypes.BOOLEAN
    else:
        return FieldTypes.UNSUPPORTED


def main():
    print("Test utils.py ...")
    ftype = 'uint'
    print(f"Field type: {ftype}")
    matched_type = match_field_type(ftype)
    print(f"Match FieldTypes.INTEGER: {matched_type is FieldTypes.INTEGER}")
    print(f"Match FieldTypes.DECIMAL: {matched_type is FieldTypes.DECIMAL}")
    print(f"Match with FieldTypes.INTEGER for FieldTypes.NUMERIC: {matched_type | FieldTypes.INTEGER is FieldTypes.NUMERIC}")
    print(f"Match with FieldTypes.DECIMAL for FieldTypes.NUMERIC: {matched_type | FieldTypes.DECIMAL is FieldTypes.NUMERIC}")
    print(matched_type | FieldTypes.DECIMAL is FieldTypes.NUMERIC or matched_type | FieldTypes.INTEGER is FieldTypes.NUMERIC)


if __name__ == "__main__":
    main()
