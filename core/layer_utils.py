# -*- coding: utf-8 -*-

from qgis.core import QgsVectorLayer


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
        raise NameError(f"{field_name} does not correspond to a field of the f{layer.name()}")

    idx = layer.fields().indexFromName(field_name)
    field = layer.fields().at(idx)

    empty_expr_str = layer.expressionField(idx).__eq__('')
    empty_type_name = field.typeName().__eq__('')

    if not empty_expr_str and empty_type_name:
        return True
    else:
        return False
