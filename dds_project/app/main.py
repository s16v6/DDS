from fastapi import FastAPI, Request, Form, Depends, HTTPException
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import date
from typing import List, Optional

from .database import database, engine, Base, SessionLocal
from .models import Status, Type, Category, Subcategory, DDSEntry
from . import schemas

app = FastAPI()

# Статические файлы и шаблоны
app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")


@app.on_event("startup")
async def startup():
    await database.connect()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


@app.on_event("shutdown")
async def shutdown():
    await database.disconnect()


async def get_db() -> AsyncSession:
    async with SessionLocal() as session:
        yield session


# --- Вспомогательные функции ---
async def get_all_statuses(db: AsyncSession) -> List[Status]:
    result = await db.execute(select(Status).order_by(Status.name))
    return result.scalars().all()


async def get_all_types(db: AsyncSession) -> List[Type]:
    result = await db.execute(select(Type).order_by(Type.name))
    return result.scalars().all()


async def get_categories_by_type(db: AsyncSession, type_id: int) -> List[Category]:
    result = await db.execute(select(Category).where(Category.type_id == type_id).order_by(Category.name))
    return result.scalars().all()


async def get_subcategories_by_category(db: AsyncSession, category_id: int) -> List[Subcategory]:
    result = await db.execute(select(Subcategory).where(Subcategory.category_id == category_id).order_by(Subcategory.name))
    return result.scalars().all()


async def get_entries_with_filters(db: AsyncSession, filters: list, order_by=None):
    query = select(DDSEntry).where(*filters)
    if order_by:
        query = query.order_by(order_by)
    else:
        query = query.order_by(DDSEntry.date.desc())
    result = await db.execute(query)
    entries = result.scalars().all()
    # Для каждого entry подгрузить связи
    for entry in entries:
        await db.refresh(entry, ['status', 'type', 'category', 'subcategory'])
    return entries


# --- API для справочников (вспомогательные) ---
@app.get("/api/statuses/", response_model=List[schemas.StatusSchema])
async def get_statuses(db: AsyncSession = Depends(get_db)):
    return await get_all_statuses(db)


@app.get("/api/types/", response_model=List[schemas.TypeSchema])
async def get_types(db: AsyncSession = Depends(get_db)):
    return await get_all_types(db)


@app.get("/api/categories/{type_id}", response_model=List[schemas.CategorySchema])
async def get_categories(type_id: int, db: AsyncSession = Depends(get_db)):
    return await get_categories_by_type(db, type_id)


@app.get("/api/subcategories/{category_id}", response_model=List[schemas.SubcategorySchema])
async def get_subcategories(category_id: int, db: AsyncSession = Depends(get_db)):
    return await get_subcategories_by_category(db, category_id)


# --- Корневой маршрут: Отображение списка с фильтрами ---
@app.get("/", response_class=HTMLResponse)
async def index(request: Request,
                date_from: Optional[str] = None,
                date_to: Optional[str] = None,
                status_id: Optional[int] = None,
                type_id: Optional[int] = None,
                category_id: Optional[int] = None,
                subcategory_id: Optional[int] = None,
                db: AsyncSession = Depends(get_db)):

    filters = []
    if date_from:
        filters.append(DDSEntry.date >= date.fromisoformat(date_from))
    if date_to:
        filters.append(DDSEntry.date <= date.fromisoformat(date_to))
    if status_id:
        filters.append(DDSEntry.status_id == status_id)
    if type_id:
        filters.append(DDSEntry.type_id == type_id)
    if category_id:
        filters.append(DDSEntry.category_id == category_id)
    if subcategory_id:
        filters.append(DDSEntry.subcategory_id == subcategory_id)

    entries = await get_entries_with_filters(db, filters)

    statuses = await get_all_statuses(db)
    types = await get_all_types(db)
    categories = await get_categories_by_type(db, type_id) if type_id else []
    subcategories = await get_subcategories_by_category(db, category_id) if category_id else []

    return templates.TemplateResponse("index.html", {
        "request": request,
        "entries": entries,
        "statuses": statuses,
        "types": types,
        "categories": categories,
        "subcategories": subcategories,
        "filters": {
            "date_from": date_from,
            "date_to": date_to,
            "status_id": status_id,
            "type_id": type_id,
            "category_id": category_id,
            "subcategory_id": subcategory_id
        }
    })


# --- Добавление новой записи ---
@app.get("/add", response_class=HTMLResponse)
async def add_entry_form(request: Request, db: AsyncSession = Depends(get_db)):
    statuses = await get_all_statuses(db)
    types = await get_all_types(db)
    return templates.TemplateResponse("edit_entry.html", {
        "request": request,
        "entry": None,
        "statuses": statuses,
        "types": types,
        "categories": [],
        "subcategories": []
    })


@app.post("/add")
async def add_entry(
    date: str = Form(...),
    status_id: int = Form(...),
    type_id: int = Form(...),
    category_id: int = Form(...),
    subcategory_id: int = Form(...),
    amount: float = Form(...),
    comment: Optional[str] = Form(None),
    db: AsyncSession = Depends(get_db)
):
    # Проверка существования справочников
    status = await db.get(Status, status_id)
    type_ = await db.get(Type, type_id)
    category = await db.get(Category, category_id)
    subcategory = await db.get(Subcategory, subcategory_id)
    if not all([status, type_, category, subcategory]):
        raise HTTPException(status_code=400, detail="Invalid reference IDs")

    new_entry = DDSEntry(
        date=date.fromisoformat(date),
        status_id=status_id,
        type_id=type_id,
        category_id=category_id,
        subcategory_id=subcategory_id,
        amount=amount,
        comment=comment
    )
    db.add(new_entry)
    await db.commit()
    await db.refresh(new_entry)
    return RedirectResponse("/", status_code=303)


# --- Редактирование записи ---
@app.get("/edit/{entry_id}", response_class=HTMLResponse)
async def edit_entry_form(entry_id: int, request: Request, db: AsyncSession = Depends(get_db)):
    entry = await db.get(DDSEntry, entry_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found")
    await db.refresh(entry, ['status', 'type', 'category', 'subcategory'])
    statuses = await get_all_statuses(db)
    types = await get_all_types(db)
    categories = await get_categories_by_type(db, entry.type_id)
    subcategories = await get_subcategories_by_category(db, entry.category_id)
    return templates.TemplateResponse("edit_entry.html", {
        "request": request,
        "entry": entry,
        "statuses": statuses,
        "types": types,
        "categories": categories,
        "subcategories": subcategories
    })


@app.post("/edit/{entry_id}")
async def edit_entry(
    entry_id: int,
    date: str = Form(...),
    status_id: int = Form(...),
    type_id: int = Form(...),
    category_id: int = Form(...),
    subcategory_id: int = Form(...),
    amount: float = Form(...),
    comment: Optional[str] = Form(None),
    db: AsyncSession = Depends(get_db)
):
    entry = await db.get(DDSEntry, entry_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found")
    status = await db.get(Status, status_id)
    type_ = await db.get(Type, type_id)
    category = await db.get(Category, category_id)
    subcategory = await db.get(Subcategory, subcategory_id)
    if not all([status, type_, category, subcategory]):
        raise HTTPException(status_code=400, detail="Invalid reference IDs")

    entry.date = date.fromisoformat(date)
    entry.status_id = status_id
    entry.type_id = type_id
    entry.category_id = category_id
    entry.subcategory_id = subcategory_id
    entry.amount = amount
    entry.comment = comment
    await db.commit()
    return RedirectResponse("/", status_code=303)


# --- Удаление записи ---
@app.post("/delete/{entry_id}")
async def delete_entry(entry_id: int, db: AsyncSession = Depends(get_db)):
    entry = await db.get(DDSEntry, entry_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found")
    await db.delete(entry)
    await db.commit()
    return RedirectResponse("/", status_code=303)


# --- Управление справочниками ---
@app.get("/manage_refs", response_class=HTMLResponse)
async def manage_refs(request: Request, db: AsyncSession = Depends(get_db)):
    statuses = await get_all_statuses(db)
    types = await get_all_types(db)
    categories = []
    for type_obj in types:
        cats = await get_categories_by_type(db, type_obj.id)
        categories.extend(cats)
    subcategories = []
    for cat in categories:
        subs = await get_subcategories_by_category(db, cat.id)
        subcategories.extend(subs)
    return templates.TemplateResponse("manage_refs.html", {
        "request": request,
        "statuses": statuses,
        "types": types,
        "categories": categories,
        "subcategories": subcategories
    })


# Добавление справочников (упрощённо)
@app.post("/add_status")
async def add_status(name: str = Form(...), db: AsyncSession = Depends(get_db)):
    new_status = Status(name=name)
    db.add(new_status)
    await db.commit()
    return RedirectResponse("/manage_refs", status_code=303)


@app.post("/add_type")
async def add_type(name: str = Form(...), db: AsyncSession = Depends(get_db)):
    new_type = Type(name=name)
    db.add(new_type)
    await db.commit()
    return RedirectResponse("/manage_refs", status_code=303)


@app.post("/add_category")
async def add_category(name: str = Form(...), type_id: int = Form(...), db: AsyncSession = Depends(get_db)):
    new_cat = Category(name=name, type_id=type_id)
    db.add(new_cat)
    await db.commit()
    return RedirectResponse("/manage_refs", status_code=303)


@app.post("/add_subcategory")
async def add_subcategory(name: str = Form(...), category_id: int = Form(...), db: AsyncSession = Depends(get_db)):
    new_sub = Subcategory(name=name, category_id=category_id)
    db.add(new_sub)
    await db.commit()
    return RedirectResponse("/manage_refs", status_code=303)
