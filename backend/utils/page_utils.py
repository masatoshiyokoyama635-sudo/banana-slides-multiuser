"""
Page utilities - shared helpers for parsing page_ids and fetching pages
"""
from typing import List, Optional, Union
from flask import Request


def parse_page_ids_from_query(request: Request) -> List[str]:
    """
    Parse page_ids from query parameters (comma-separated string).
    
    Args:
        request: Flask request object
        
    Returns:
        List of page ID strings (empty list if none provided)
    """
    page_ids_param = request.args.get('page_ids', '')
    if not page_ids_param:
        return []
    return [pid.strip() for pid in page_ids_param.split(',') if pid.strip()]


def parse_page_ids_from_body(data: dict) -> List[str]:
    """
    Parse page_ids from request body (array of IDs).
    
    Args:
        data: Request JSON data dict
        
    Returns:
        List of page ID strings (empty list if invalid or none provided)
    """
    page_ids = data.get('page_ids', [])
    if not isinstance(page_ids, list):
        return []
    return page_ids


def get_filtered_pages(project_id: str, page_ids: Optional[List[str]] = None, user_id: Optional[str] = None):
    """
    Fetch pages for a project, optionally filtered by page IDs.

    Args:
        project_id: Project ID
        page_ids: Optional list of page IDs to filter by
        user_id: Optional user ID for ownership filtering

    Returns:
        List of Page objects ordered by order_index
    """
    from models import Page, Project

    if user_id is not None:
        query = Page.query.join(Project, Page.project_id == Project.id).filter(
            Page.project_id == project_id,
            Project.user_id == user_id,
        )
    else:
        query = Page.query.filter(Page.project_id == project_id)

    if page_ids:
        query = query.filter(Page.id.in_(page_ids))

    return query.order_by(Page.order_index).all()

