#!/usr/bin/env python

from inspect import iscoroutinefunction

from lxml import etree
from typing import Any

from ruia.exceptions import InvalidFuncType
from ruia.field import BaseField
from ruia.request import Request


class ItemMeta(type):
    """
    Metaclass for an item
    """

    def __new__(cls, name, bases, attrs):
        __fields = dict({(field_name, attrs.pop(field_name)) for field_name, object in list(attrs.items()) if
                         isinstance(object, BaseField)})
        attrs['__fields'] = __fields
        new_class = type.__new__(cls, name, bases, attrs)
        return new_class


class Item(metaclass=ItemMeta):
    """
    Item class for each item
    """

    def __init__(self):
        self.results = {}

    @classmethod
    async def _get_html(cls, html: str = '', url: str = '', **kwargs):
        if html or url:
            if url:
                sem = kwargs.pop('sem', None)
                request = Request(url, **kwargs)
                if sem:
                    _, response = await request.fetch_callback(sem=sem)
                else:
                    response = await request.fetch()
                html = response.html
            return etree.HTML(html)
        else:
            ValueError("html(url or html_etree) is expected")

    @classmethod
    async def _parse_html(cls, *, html_etree: etree._Element) -> object:
        if html_etree is None:
            raise ValueError("html_etree is expected")
        item_ins = cls()
        for field_name, field_value in getattr(item_ins, '__fields', {}).items():
            if not field_name.startswith('target_'):
                clean_method = getattr(item_ins, f'clean_{field_name}', None)
                value = field_value.extract(html_etree=html_etree)
                if clean_method is not None:
                    if iscoroutinefunction(clean_method):
                        value = await clean_method(value)
                    else:
                        raise InvalidFuncType('clean_method must be a coroutine function')
                setattr(item_ins, field_name, value)
                item_ins.results[field_name] = value
        return item_ins

    @classmethod
    async def get_item(cls, *,
                       html: str = '',
                       url: str = '',
                       html_etree: etree._Element = None,
                       **kwargs) -> Any:
        if html_etree is None:
            html_etree = await cls._get_html(html, url, **kwargs)

        return await cls._parse_html(html_etree=html_etree)

    @classmethod
    async def get_items(cls, *,
                        html: str = '',
                        url: str = '',
                        html_etree: etree._Element = None,
                        **kwargs):
        if html_etree is None:
            html_etree = await cls._get_html(html, url, **kwargs)
        items_field = getattr(cls, '__fields', {}).get('target_item', None)
        if items_field:
            items_field.many = True
            items_html_etree = items_field.extract(html_etree=html_etree, is_source=True)
            if items_html_etree:
                for each_html_etree in items_html_etree:
                    item = await cls._parse_html(html_etree=each_html_etree)
                    yield item
                # all_items = []
                # for each_html_etree in items:
                #     all_items.append(await cls._parse_html(html_etree=each_html_etree))
                # return all_items
            else:
                raise ValueError("Get target_item's value error!")
        else:
            raise ValueError("target_item is expected")

    def __str__(self):
        return f"<Item {self.results}>"
