from decimal import Decimal

import pytest

from modules.data_migration.domain.entities.import_job import FieldMapping, apply_field_mappings
from modules.data_migration.domain.value_objects.enums import TargetEntity


def test_apply_field_mappings_basic():
    row = {"CustName": "  شركة الفا  ", "CustPhone": "0770000000"}
    mappings = [
        FieldMapping(TargetEntity.PARTNERS, "CustName", "name", transform="strip_or_none"),
        FieldMapping(TargetEntity.PARTNERS, "CustPhone", "phone"),
    ]
    result = apply_field_mappings(row, mappings, target_entity=TargetEntity.PARTNERS)
    assert result == {"name": "شركة الفا", "phone": "0770000000"}


def test_apply_field_mappings_ignores_other_entities():
    row = {"A": "1", "B": "2"}
    mappings = [
        FieldMapping(TargetEntity.PARTNERS, "A", "x"),
        FieldMapping(TargetEntity.CATALOG_ITEMS, "B", "y"),
    ]
    result = apply_field_mappings(row, mappings, target_entity=TargetEntity.PARTNERS)
    assert result == {"x": "1"}  # عمود الكيان الآخر لا يظهر إطلاقاً


def test_decimal_or_zero_transform():
    row = {"Price": "125.500"}
    mappings = [FieldMapping(TargetEntity.CATALOG_ITEMS, "Price", "sale_price", transform="decimal_or_zero")]
    result = apply_field_mappings(row, mappings, target_entity=TargetEntity.CATALOG_ITEMS)
    assert result["sale_price"] == Decimal("125.500")


def test_decimal_or_zero_empty_value_defaults_to_zero():
    row = {"Price": None}
    mappings = [FieldMapping(TargetEntity.CATALOG_ITEMS, "Price", "sale_price", transform="decimal_or_zero")]
    result = apply_field_mappings(row, mappings, target_entity=TargetEntity.CATALOG_ITEMS)
    assert result["sale_price"] == Decimal(0)


def test_unknown_transform_raises():
    row = {"A": "1"}
    mappings = [FieldMapping(TargetEntity.PARTNERS, "A", "x", transform="does_not_exist")]
    with pytest.raises(ValueError, match="دالة تحويل غير معروفة"):
        apply_field_mappings(row, mappings, target_entity=TargetEntity.PARTNERS)
