# Alchemy FilterSet 🚀

A powerful, dynamic, and type-safe filtering architecture for **SQLAlchemy 2.0** and **Advanced Alchemy**, heavily inspired by `django-filters`.

## Why Alchemy FilterSet?

While SQLAlchemy and Advanced Alchemy provide excellent tools for querying databases, handling complex HTTP query parameters (like nested relationships, dynamic ordering, and multi-field search) often leads to messy, repetitive, and hard-to-maintain code.

`alchemy-filterset` bridges the gap between your Web Framework (FastAPI, Litestar, etc.) and your Database by providing a declarative, Pydantic-powered filter class that securely translates user requests into highly optimized SQL `EXISTS` subqueries.

## Key Features

- 🔗 **Deep Nested Relationships:** Seamlessly filter across infinite layers of relationships (e.g., `province__country__name__icontains="Iran"`).
- 🚫 **Negation Support:** Easily exclude records using the `not__` prefix (e.g., `not__status="deleted"`).
- 🗂 **Smart Pagination:** Built-in, declarative pagination controls with frontend limits and backend enforcement.
- 🔍 **Global Multi-Field Search:** Search across multiple columns and related tables simultaneously with a single `?search=` parameter.
- ↕️ **Dynamic Ordering:** Sort by any field or nested relationship (e.g., `?ordering=-province__name,created_at`).
- 🧩 **Association Proxy Support:** Fully supports querying and ordering across SQLAlchemy's `AssociationProxy`.
- 🛡 **Type-Safe:** Built with Pydantic v2 and Python 3.10+ types.

---

## 📦 Installation

This package requires Python 3.10+ and SQLAlchemy 2.0+.

```bash
pip install alchemy-filterset
uv add alchemy-filterset
```

*(Or use `uv add alchemy-filterset` / `poetry add alchemy-filterset`)*

---

## ⚡ Quick Start

Imagine you have two SQLAlchemy models: `Country` and `Province`.

### 1. Define your FilterSet

Inherit from `SQLAlchemyFilterSet` and declare the allowed filters as Pydantic fields.

```python
from uuid import UUID
from alchemy_filterset import SQLAlchemyFilterSet
from my_app.models import Province

class ProvinceFilter(SQLAlchemyFilterSet):
    # 1. Bind to your SQLAlchemy Model
    model_cls = Province
    
    # 2. Define fields for global search (?search=...)
    search_fields = {"name", "country__name", "country__code"}

    # 3. Define allowed query parameters using double-underscore syntax
    name__icontains: str | None = None
    population__gt: int | None = None
    is_active: bool | None = None
    
    # 4. Filter across relationships seamlessly!
    country__id: UUID | None = None
    country__code__in: list[str] | None = None
```

### 2. Use it in your API (FastAPI / Litestar Example)

Pass the query parameters to the FilterSet, call `to_statement_filters()`, and pass the result to your Advanced Alchemy repository.

```python
# Example using FastAPI/Litestar dependency injection
@app.get("/provinces")
async def get_provinces(
    filters: ProvinceFilter = Depends(), 
    repo: ProvinceRepository = Depends()
):
    # 1. Translate Pydantic model to SQLAlchemy expressions
    sql_filters = filters.to_statement_filters()
    
    # 2. Pass them to Advanced Alchemy repository
    provinces = await repo.get_many(*sql_filters)
    
    return provinces
```

Now, your API automatically supports queries like:
`GET /provinces?country__code__in=IR,US&population__gt=1000000&ordering=-name&page=2`

---

## 📖 Feature Guide & Examples

### 1. Standard Lookups

By default, fields use the exact equality (`eq`) operator. You can append lookups using the `__` syntax.

Supported Lookups:

- **Comparison:** `eq`, `ne`, `gt`, `ge`, `lt`, `le`, `between`
- **Collection:** `in`, `notin`
- **Text:** `contains`, `icontains`, `not_contains`, `not_icontains`, `startswith`, `endswith`
- **Null Check:** `is_null`, `not_null`

```http
GET /api/users?age__between=18,30
GET /api/users?status__in=active,pending
GET /api/users?email__endswith=@gmail.com
GET /api/users?deleted_at__is_null=true
```

### 2. Negation / Exclude (The `not__` prefix)

You can negate any standard lookup, nested relationship, or custom filter simply by prefixing it with `not__`.
This dynamically translates to `!=`, `NOT IN`, or `NOT EXISTS` in SQL.

```python
class UserFilter(SQLAlchemyFilterSet):
    model_cls = User
    
    # Simple Negation (e.g., status != 'banned')
    not__status: str | None = None
    
    # Nested Negation (Users who DO NOT have a specific role)
    not__roles__name__icontains: str | None = None
```

### 3. Deep Nested Relationships (The Magic ✨)

You don't need to write complex `JOIN`s or `EXISTS` subqueries manually. Just chain relationship names separated by `__`.

```python
class CityFilter(SQLAlchemyFilterSet):
    model_cls = City
    
    # City -> Province -> Country -> name
    province__country__name__icontains: str | None = None
```

Under the hood, this generates highly optimized SQL `EXISTS` queries using SQLAlchemy's `.has()` and `.any()`.

### 4. Global Search

Define `search_fields` on your class. If a user passes the `?search=` parameter, the system will apply an `icontains` filter to all specified fields, joining them with an `OR` operator.

```python
class PostFilter(SQLAlchemyFilterSet):
    model_cls = Post
    search_fields = {"title", "content", "author__username"}
```

`GET /api/posts?search=python` will search for "python" in the title, content, OR the author's username.

### 5. Dynamic Ordering

Users can sort results using the `ordering` parameter. Prefix with `-` for descending order. Separate multiple fields with commas.

`GET /api/users?ordering=-created_at,last_name`

### 6. Pagination Control

Pagination is enabled by default. If the user does not provide `page` or `page_size`, the defaults are used.

```python
class HeavyReportFilter(SQLAlchemyFilterSet):
    model_cls = Report
    
    # Customize pagination limits per class
    default_page_size = 10
    max_page_size = 50 
```

**Disabling Pagination:**
If an API should return all records (e.g., a dropdown list), set `enable_pagination = False`.

```python
class DropdownFilter(SQLAlchemyFilterSet):
    model_cls = Category
    enable_pagination = False # Limits/Offsets are entirely ignored
```

### 7. Custom Filter Methods

Need complex logic that doesn't fit standard lookups? Write a custom method! Name it `filter_<field_name>`.

```python
class UserFilter(SQLAlchemyFilterSet):
    model_cls = User
    
    has_avatar: bool | None = None

    def filter_has_avatar(self, value: bool):
        if value:
            return User.avatar_url.is_not(None)
        return User.avatar_url.is_(None)
```

---

## 🛠 Advanced Usage: Association Proxies

`alchemy-filterset` natively supports SQLAlchemy's `AssociationProxy`. It automatically unpacks the proxy, discovers the underlying tables, and applies the filters or ordering correctly without crashing.

```python
class Post(Base):
    __tablename__ = "posts"
    # ...
    # Association proxy to tags
    tags: AssociationProxy[list[str]] = association_proxy("post_tags", "tag_name")

class PostFilter(SQLAlchemyFilterSet):
    model_cls = Post
    # Works perfectly!
    tags__icontains: str | None = None
```

## License

MIT
