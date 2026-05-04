"""
Material Controller - handles standalone material image generation
"""
from flask import Blueprint, request, current_app, send_file
from models import db, Project, Material, Task
from utils import success_response, error_response, not_found, bad_request
from utils.auth import current_user_id, get_current_user_project
from services import FileService
from services.user_ai import create_user_ai_service, get_user_ai_config
from services.task_manager import task_manager, generate_material_image_task
from pathlib import Path
from werkzeug.utils import secure_filename
from typing import Optional
import tempfile
import shutil
import time
import zipfile
import logging

logger = logging.getLogger(__name__)

material_bp = Blueprint('materials', __name__, url_prefix='/api/projects')
material_global_bp = Blueprint('materials_global', __name__, url_prefix='/api/materials')

ALLOWED_MATERIAL_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.gif', '.webp', '.bmp', '.svg'}
ALLOWED_ASPECT_RATIOS = frozenset({'16:9', '21:9', '4:3', '3:2', '5:4', '1:1', '4:5', '2:3', '3:4', '9:16'})


def _generate_image_caption(filepath: str) -> str:
    """Generate AI caption for an uploaded image. Returns empty string on failure."""
    if filepath.lower().endswith('.svg'):
        return ""
    try:
        config = get_user_ai_config(current_user_id())
        if config.output_language == 'en':
            prompt = "Please provide a short description of the main content of this image. Return only the description text without any other explanation."
        else:
            prompt = "请用一句简短的中文描述这张图片的主要内容。只返回描述文字，不要其他解释。"

        return create_user_ai_service(current_user_id())._generate_text_from_image(prompt, filepath)
    except Exception as e:
        logger.warning(f"Failed to generate caption for {filepath}: {e}")
        return ""


def _get_user_project_or_404(project_id: str):
    project = get_current_user_project(project_id)
    if not project:
        return None, not_found('Project')
    return project, None


def _build_material_query(filter_project_id: str):
    """Build common material query with project validation."""
    user_id = current_user_id()
    query = Material.query.filter(Material.user_id == user_id)

    if filter_project_id == 'all':
        return query, None
    if filter_project_id == 'none':
        return query.filter(Material.project_id.is_(None)), None

    project, error = _get_user_project_or_404(filter_project_id)
    if error:
        return None, error

    return query.filter(Material.project_id == project.id), None


def _get_materials_list(filter_project_id: str):
    """
    Common logic to get materials list.
    Returns (materials_list, error_response)
    """
    query, error = _build_material_query(filter_project_id)
    if error:
        return None, error
    
    materials = query.order_by(Material.created_at.desc()).all()
    materials_list = [material.to_dict() for material in materials]
    
    return materials_list, None


def _handle_material_upload(default_project_id: Optional[str] = None):
    """
    Common logic to handle material upload.
    Returns Flask response object.
    """
    try:
        raw_project_id = request.args.get('project_id', default_project_id)
        target_project_id, error = _resolve_target_project_id(raw_project_id)
        if error:
            return error

        file = request.files.get('file')
        material, error = _save_material_file(file, target_project_id)
        if error:
            return error

        result = material.to_dict()

        # Generate AI caption if requested
        generate_caption = request.args.get('generate_caption', '').lower() in ('true', '1', 'yes')
        if generate_caption:
            file_service = FileService(current_app.config['UPLOAD_FOLDER'])
            filepath = file_service.get_absolute_path(material.relative_path)
            caption = _generate_image_caption(filepath)
            material.caption = caption
            db.session.commit()
            result['caption'] = caption

        return success_response(result, status_code=201)

    except Exception as e:
        db.session.rollback()
        return error_response('SERVER_ERROR', str(e), 500)


def _resolve_target_project_id(raw_project_id: Optional[str], allow_none: bool = True):
    """
    Normalize project_id from request.
    Returns (project_id | None, error_response | None)
    """
    if allow_none and (raw_project_id is None or raw_project_id == 'none'):
        return None, None

    if raw_project_id == 'all':
        return None, bad_request("project_id cannot be 'all' when uploading materials")

    if raw_project_id:
        project, error = _get_user_project_or_404(raw_project_id)
        if error:
            return None, error

    return raw_project_id, None


def _save_material_file(file, target_project_id: Optional[str]):
    """Shared logic for saving uploaded material files to disk and DB."""
    if not file or not file.filename:
        return None, bad_request("file is required")

    filename = secure_filename(file.filename)
    file_ext = Path(filename).suffix.lower()
    if file_ext not in ALLOWED_MATERIAL_EXTENSIONS:
        return None, bad_request(f"Unsupported file type. Allowed: {', '.join(sorted(ALLOWED_MATERIAL_EXTENSIONS))}")

    file_service = FileService(current_app.config['UPLOAD_FOLDER'])
    if target_project_id:
        materials_dir = file_service.upload_folder / file_service._get_materials_dir(target_project_id)
    else:
        materials_dir = file_service.upload_folder / "materials"
    materials_dir.mkdir(exist_ok=True, parents=True)

    timestamp = int(time.time() * 1000)
    base_name = Path(filename).stem
    unique_filename = f"{base_name}_{timestamp}{file_ext}"

    filepath = materials_dir / unique_filename
    file.save(str(filepath))

    relative_path = str(filepath.relative_to(file_service.upload_folder))
    if target_project_id:
        image_url = file_service.get_file_url(target_project_id, 'materials', unique_filename)
    else:
        image_url = f"/files/materials/{unique_filename}"

    material = Material(
        user_id=current_user_id(),
        project_id=target_project_id,
        filename=unique_filename,
        relative_path=relative_path,
        url=image_url,
        original_filename=filename
    )

    try:
        db.session.add(material)
        db.session.commit()
        return material, None
    except Exception:
        db.session.rollback()
        raise


@material_bp.route('/<project_id>/materials/generate', methods=['POST'])
def generate_material_image(project_id):
    """
    POST /api/projects/{project_id}/materials/generate - Generate a standalone material image

    Supports multipart/form-data:
    - prompt: Text-to-image prompt (passed directly to the model without modification)
    - ref_image: Main reference image (optional)
    - extra_images: Additional reference images (multiple files, optional)
    
    Note: project_id can be 'none' to generate global materials (not associated with any project)
    """
    try:
        # 支持 'none' 作为特殊值，表示生成用户级素材
        if project_id != 'none':
            project, error = _get_user_project_or_404(project_id)
            if error:
                return error
        else:
            project = None
            project_id = None

        # Parse request data (prioritize multipart for file uploads)
        if request.is_json:
            data = request.get_json() or {}
            prompt = data.get('prompt', '').strip()
            ref_file = None
            extra_files = []
        else:
            data = request.form.to_dict()
            prompt = (data.get('prompt') or '').strip()
            ref_file = request.files.get('ref_image')
            extra_files = request.files.getlist('extra_images') or []

        aspect_ratio = (data.get('aspect_ratio') or '').strip() or None
        if aspect_ratio and aspect_ratio not in ALLOWED_ASPECT_RATIOS:
            return bad_request(f"Invalid aspect ratio. Allowed values: {', '.join(sorted(ALLOWED_ASPECT_RATIOS))}")

        if not prompt:
            return bad_request("prompt is required")

        task_project_id = project_id if project_id is not None else None

        # Initialize services
        ai_service = create_user_ai_service(current_user_id())
        file_service = FileService(current_app.config['UPLOAD_FOLDER'])

        # 创建临时目录保存参考图片（后台任务会清理）
        temp_dir = Path(tempfile.mkdtemp(dir=current_app.config['UPLOAD_FOLDER']))
        temp_dir_str = str(temp_dir)

        try:
            ref_path = None
            # Save main reference image to temp directory if provided
            if ref_file and ref_file.filename:
                ref_filename = secure_filename(ref_file.filename or 'ref.png')
                ref_path = temp_dir / ref_filename
                ref_file.save(str(ref_path))
                ref_path_str = str(ref_path)
            else:
                ref_path_str = None

            # Save additional reference images to temp directory
            additional_ref_images = []
            for extra in extra_files:
                if not extra or not extra.filename:
                    continue
                extra_filename = secure_filename(extra.filename)
                extra_path = temp_dir / extra_filename
                extra.save(str(extra_path))
                additional_ref_images.append(str(extra_path))

            # Create async task for material generation
            task = Task(
                user_id=current_user_id(),
                project_id=task_project_id,
                task_type='GENERATE_MATERIAL',
                status='PENDING'
            )
            task.set_progress({
                'total': 1,
                'completed': 0,
                'failed': 0
            })
            db.session.add(task)
            db.session.commit()

            # Get app instance for background task
            app = current_app._get_current_object()

            # Submit background task
            task_manager.submit_task(
                task.id,
                generate_material_image_task,
                task_project_id,
                prompt,
                ai_service,
                file_service,
                ref_path_str,
                additional_ref_images if additional_ref_images else None,
                aspect_ratio or (project.image_aspect_ratio if project else None) or current_app.config.get('DEFAULT_ASPECT_RATIO', '16:9'),
                current_app.config['DEFAULT_RESOLUTION'],
                temp_dir_str,
                app
            )

            # Return task_id immediately (不再清理temp_dir，由后台任务清理)
            return success_response({
                'task_id': task.id,
                'status': 'PENDING'
            }, status_code=202)
        
        except Exception as e:
            # Clean up temp directory on error
            if temp_dir.exists():
                shutil.rmtree(temp_dir, ignore_errors=True)
            raise

    except Exception as e:
        db.session.rollback()
        return error_response('AI_SERVICE_ERROR', str(e), 503)


@material_bp.route('/<project_id>/materials', methods=['GET'])
def list_materials(project_id):
    """
    GET /api/projects/{project_id}/materials - List materials for a specific project
    
    Returns:
        List of material images with filename, url, and metadata for the specified project
    """
    try:
        materials_list, error = _get_materials_list(project_id)
        if error:
            return error
        
        return success_response({
            "materials": materials_list,
            "count": len(materials_list)
        })
    
    except Exception as e:
        return error_response('SERVER_ERROR', str(e), 500)


@material_bp.route('/<project_id>/materials/upload', methods=['POST'])
def upload_material(project_id):
    """
    POST /api/projects/{project_id}/materials/upload - Upload a material image
    
    Supports multipart/form-data:
    - file: Image file (required)
    - project_id: Optional query parameter, defaults to path parameter if not provided
    
    Returns:
        Material info with filename, url, and metadata
    """
    return _handle_material_upload(default_project_id=project_id)


@material_global_bp.route('', methods=['GET'])
def list_all_materials():
    """
    GET /api/materials - Global materials endpoint for complex queries
    
    Query params:
        - project_id: Filter by project_id
          * 'all' (default): Get all materials regardless of project
          * 'none': Get only materials without a project (global materials)
          * <project_id>: Get materials for specific project
    
    Returns:
        List of material images with filename, url, and metadata
    """
    try:
        filter_project_id = request.args.get('project_id', 'all')
        materials_list, error = _get_materials_list(filter_project_id)
        if error:
            return error
        
        return success_response({
            "materials": materials_list,
            "count": len(materials_list)
        })
    
    except Exception as e:
        return error_response('SERVER_ERROR', str(e), 500)


@material_global_bp.route('/upload', methods=['POST'])
def upload_material_global():
    """
    POST /api/materials/upload - Upload a material image (global, not bound to a project)
    
    Supports multipart/form-data:
    - file: Image file (required)
    - project_id: Optional query parameter to associate with a project
    
    Returns:
        Material info with filename, url, and metadata
    """
    return _handle_material_upload(default_project_id=None)


@material_global_bp.route('/<material_id>', methods=['DELETE'])
def delete_material(material_id):
    """
    DELETE /api/materials/{material_id} - Delete a material and its file
    """
    try:
        material = Material.query.filter_by(id=material_id, user_id=current_user_id()).first()
        if not material:
            return not_found('Material')

        file_service = FileService(current_app.config['UPLOAD_FOLDER'])
        material_path = Path(file_service.get_absolute_path(material.relative_path))

        # First, delete the database record to ensure data consistency
        db.session.delete(material)
        db.session.commit()

        # Then, attempt to delete the file. If this fails, log the error
        # but still return a success response. This leaves an orphan file,
        try:
            if material_path.exists():
                material_path.unlink(missing_ok=True)
        except OSError as e:
            current_app.logger.warning(f"Failed to delete file for material {material_id} at {material_path}: {e}")

        return success_response({"id": material_id})
    except Exception as e:
        db.session.rollback()
        return error_response('SERVER_ERROR', str(e), 500)


@material_global_bp.route('/associate', methods=['POST'])
def associate_materials_to_project():
    """
    POST /api/materials/associate - Associate materials to a project by URLs

    Request body (JSON):
    {
        "project_id": "project_id",
        "material_urls": ["url1", "url2", ...]
    }

    Returns:
        List of associated material IDs and count
    """
    try:
        data = request.get_json() or {}
        project_id = data.get('project_id')
        material_urls = data.get('material_urls', [])

        if not project_id:
            return bad_request("project_id is required")

        if not material_urls or not isinstance(material_urls, list):
            return bad_request("material_urls must be a non-empty array")

        # Validate project exists
        project, error = _get_user_project_or_404(project_id)
        if error:
            return error

        # Find materials by URLs and update their project_id
        updated_ids = []
        materials_to_update = Material.query.filter(
            Material.user_id == current_user_id(),
            Material.url.in_(material_urls),
            Material.project_id.is_(None)
        ).all()
        for material in materials_to_update:
            material.project_id = project.id
            updated_ids.append(material.id)

        db.session.commit()

        return success_response({
            "updated_ids": updated_ids,
            "count": len(updated_ids)
        })

    except Exception as e:
        db.session.rollback()
        return error_response('SERVER_ERROR', str(e), 500)


@material_global_bp.route('/download', methods=['POST'])
def download_materials_zip():
    """Bundle requested materials into a ZIP and stream it back."""
    body = request.get_json(silent=True) or {}
    ids = body.get('material_ids')

    if not ids or not isinstance(ids, list):
        return bad_request("material_ids must be a non-empty list")

    MAX_BATCH = 200
    if len(ids) > MAX_BATCH:
        return bad_request(f"Too many materials requested (max {MAX_BATCH})")

    rows = Material.query.filter(
        Material.user_id == current_user_id(),
        Material.id.in_(ids)
    ).all()
    if not rows:
        return not_found('Materials')

    tmp = tempfile.SpooledTemporaryFile(max_size=64 * 1024 * 1024)
    try:
        fs = FileService(current_app.config['UPLOAD_FOLDER'])

        with zipfile.ZipFile(tmp, 'w', zipfile.ZIP_DEFLATED) as zf:
            for row in rows:
                abs_path = Path(fs.get_absolute_path(row.relative_path))
                if not abs_path.is_file():
                    current_app.logger.warning("Skipping missing file for material %s", row.id)
                    continue
                zf.write(str(abs_path), row.filename)

        tmp.seek(0)
        fname = f"materials_{int(time.time())}.zip"

        return send_file(tmp, mimetype='application/zip',
                         as_attachment=True, download_name=fname)
    except Exception:
        tmp.close()
        current_app.logger.exception("Failed to build materials zip")
        return error_response('SERVER_ERROR', 'Failed to create zip archive', 500)


@material_global_bp.route('/<material_id>/caption', methods=['GET'])
def get_material_caption(material_id):
    """Get or generate caption for an existing material"""
    material = Material.query.filter_by(id=material_id, user_id=current_user_id()).first()
    if not material:
        return not_found('Material')

    # Return existing caption if available (None=not yet generated, ''=failed)
    if material.caption is not None:
        return success_response({'caption': material.caption})

    # Generate and store caption
    try:
        file_service = FileService(current_app.config['UPLOAD_FOLDER'])
        filepath = file_service.get_absolute_path(material.relative_path)
        caption = _generate_image_caption(filepath)
        material.caption = caption
        db.session.commit()
        return success_response({'caption': caption})
    except Exception as e:
        db.session.rollback()
        return error_response('SERVER_ERROR', str(e), 500)


@material_global_bp.route('/by-url', methods=['GET'])
def get_material_by_url():
    """Get material by URL and ensure it has a caption"""
    url = request.args.get('url', '').strip()
    if not url:
        return bad_request('url parameter is required')

    material = Material.query.filter_by(url=url, user_id=current_user_id()).first()
    if not material:
        return not_found('Material')

    # Ensure caption exists (None=not yet generated, ''=failed)
    try:
        if material.caption is None:
            file_service = FileService(current_app.config['UPLOAD_FOLDER'])
            filepath = file_service.get_absolute_path(material.relative_path)
            material.caption = _generate_image_caption(filepath)
            db.session.commit()
        return success_response(material.to_dict())
    except Exception as e:
        db.session.rollback()
        return error_response('SERVER_ERROR', str(e), 500)

