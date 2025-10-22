from dataclasses import dataclass, asdict, field
from typing import Dict, List, Tuple
from urllib.parse import urlencode
from variables import addon_icon, addon_fanart

@dataclass
class Item:
    title: str = 'Unknown Title'
    type: str = 'item'
    mode: str = ''
    link: str = ''
    thumbnail: str = addon_icon
    fanart: str = addon_fanart
    summary: str = ''
    contextmenu: List[Tuple[str]] = field(default_factory=list)
    title2: str = ''
    
    
    def to_dict(self) -> Dict:
        return {k: v for k, v in asdict(self).items() if v}
    
    def full_dict(self) -> Dict:
        return asdict(self)
    
    def url_encode(self) -> str:
        return urlencode(self.to_dict())


@dataclass
class Channel(Item):
    def __post_init__(self):
        self.mode = 'play'


@dataclass
class Category(Item):
    def __post_init__(self):
        self.type = 'dir'
        self.mode='matches'
        