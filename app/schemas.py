from datetime import datetime, timezone, date
from typing import Literal
from pydantic import BaseModel, Field, ConfigDict, field_validator


class Strict(BaseModel):
    model_config = ConfigDict(extra='forbid')


class NodeIn(Strict):
    id: str = Field(pattern=r'^[A-Za-z0-9_-]{1,80}$')
    label: str = Field(min_length=1, max_length=200)
    kind: Literal['Person', 'Phone', 'Organization', 'Vehicle', 'Location', 'Event', 'Case', 'Transaction']
    attrs: dict[str, str] = Field(default_factory=dict, max_length=12)


class SourceIn(Strict):
    id: str = Field(pattern=r'^[A-Za-z0-9_-]{1,80}$')
    title: str = Field(min_length=1, max_length=200)
    text: str = Field(min_length=1, max_length=2000000)


class EdgeIn(Strict):
    id: str = Field(pattern=r'^[A-Za-z0-9_-]{1,80}$')
    source: str = Field(max_length=80)
    target: str = Field(max_length=80)
    relation: Literal['called', 'met', 'owns', 'uses', 'visited', 'member_of', 'transferred', 'mentioned_in']
    source_id: str = Field(max_length=80)
    excerpt: str = Field(min_length=1, max_length=10000)
    occurred_at: str | None = None
    polarity: Literal['asserted', 'denied', 'uncertain'] = 'asserted'

    @field_validator('occurred_at')
    @classmethod
    def aware(cls, value):
        if value is None or value == '': return None
        if len(value) == 10: return date.fromisoformat(value).isoformat()
        d = datetime.fromisoformat(value.replace('Z', '+00:00'))
        if d.tzinfo is None: raise ValueError('Timestamp needs timezone, or use YYYY-MM-DD / null for unknown time')
        return d.astimezone(timezone.utc).isoformat()


class Bundle(Strict):
    entities: list[NodeIn] = Field(default_factory=list, max_length=50000)
    sources: list[SourceIn] = Field(default_factory=list, max_length=50000)
    edges: list[EdgeIn] = Field(default_factory=list, max_length=50000)


class ReviewIn(Strict):
    decision: Literal['accepted', 'rejected', 'pending']
    reason: str = Field(min_length=5, max_length=10000)
    expected_revision: int = Field(ge=0)


class TextIn(Strict):
    text: str = Field(min_length=1, max_length=20000)
    mode: Literal['rules', 'transformer'] = 'rules'


class CaseIn(Strict):
    title: str = Field(min_length=1, max_length=200)


class ConvertIn(Strict):
    text: str = Field(min_length=1, max_length=24000000)
    format: Literal['auto', 'text', 'csv', 'json', 'jsonl'] = 'auto'
    title: str = Field(default='User supplied record', min_length=1, max_length=200)
    default_time: datetime | None = None
    column_map: dict[str, str] = Field(default_factory=dict)
    timezone_offset: str = Field(default='+05:30', pattern=r'^[+-](?:0[0-9]|1[0-4]):[0-5][0-9]$')

    @field_validator('default_time')
    @classmethod
    def aware_default(cls, value):
        if value is not None and value.tzinfo is None:
            raise ValueError('Select a timestamp with timezone')
        return value


class NodeEdit(Strict):
    label: str = Field(min_length=1, max_length=200)
    attrs: dict[str, str] = Field(default_factory=dict, max_length=12)
    expected_label: str
    expected_attrs: dict[str, str]


class EdgeEdit(Strict):
    relation: Literal['called','met','owns','uses','visited','member_of','transferred','mentioned_in']
    occurred_at: str | None = None
    polarity: Literal['asserted','denied','uncertain']
    expected_revision: int = Field(ge=0)
    reason: str = Field(min_length=5, max_length=2000)
    _aware = field_validator('occurred_at')(EdgeIn.aware.__func__)


class BatchReview(Strict):
    edges: list[dict[str, int | str]] = Field(min_length=1, max_length=50000)
    decision: Literal['accepted','rejected','pending']
    reason: str = Field(min_length=5, max_length=2000)
