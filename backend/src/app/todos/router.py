from typing import Dict, List

from fastapi import APIRouter, HTTPException

from src.app.todos.domains import TodoCreate, TodoRead, TodoUpdate
from src.app.todos.models import Todo
from src.network.database.repository.exceptions import RepositoryObjectNotFound

router = APIRouter()


@router.get('/list-todos')
def list_todos() -> List[TodoRead]:
    return Todo.list()


@router.get('/get-todo/{todo_id}')
def get_todo(todo_id: str) -> TodoRead:
    try:
        return Todo.get(Todo.id == todo_id)
    except RepositoryObjectNotFound:
        raise HTTPException(status_code=404, detail='Todo not found')


@router.post('/create-todo')
def create_todo(todo: TodoCreate) -> TodoRead:
    return Todo.create(todo)


@router.patch('/update-todo/{todo_id}')
def update_todo(todo_id: str, todo: TodoUpdate) -> TodoRead:
    try:
        # Get the existing todo first
        existing_todo = Todo.get(Todo.id == todo_id)
        # Update only the fields that were provided
        updates = todo.model_dump(exclude_unset=True)
        if updates:
            return Todo.update(todo_id, **updates)
        return existing_todo
    except RepositoryObjectNotFound:
        raise HTTPException(status_code=404, detail='Todo not found')


@router.delete('/delete-todo/{todo_id}')
def delete_todo(todo_id: str) -> Dict[str, str]:
    try:
        Todo.delete(Todo.id == todo_id)
        return {'message': 'Todo deleted successfully'}
    except RepositoryObjectNotFound:
        raise HTTPException(status_code=404, detail='Todo not found')
