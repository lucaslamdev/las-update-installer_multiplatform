"""HTTP route handlers for the LAS Update Installer API.

Matches Java handler behavior:
- Authentication on all protected routes
- Correct HTTP status codes (202 for registry, 406 for IllegalState)
- GET /modules/<release> for checking single module
- DELETE /modules/<release> for deleting module
- Info endpoint returns release, os, _links (not name/version/description)
- Discovery routes use server token auth
- Module routes use MvupdateKey auth
- Connect uses server token auth
"""

from __future__ import annotations
import json
import logging
import platform

from flask import request, jsonify, Response

from config import BUILD_NAME, BUILD_VERSION
from environment import EnvironmentConfiguration
from utils.hostname_utils import get_hostname
from managers.discovery_manager import DiscoveryManagerImpl
from managers.module_manager import ModuleManagerImpl
from models import (
    ModuleExistsException,
    ModuleIllegalStateException,
    ModuleNotFoundException,
    InstanceInfoExistsException,
    InstanceInfoNotFoundException,
)
from models.dto import ServerInfo, LinkResource, ErrorInfo
from models.instance_info import InstanceInfo
from models.module_status import ModuleStatus
from models.mvupdate_key import MvupdateKey
from repositories.mvupdate_key_repository import MvupdateKeyRepositoryImpl
from repositories.server_config_repository import ServerConfigRepositoryProperties

logger = logging.getLogger(__name__)


def register_handlers(app_server):
    """Register all HTTP handlers on the app server."""

    # ==========================================
    # GET / - Server info (requires MvupdateKey auth)
    # Java: InfoServerHandler extends MvUpdateKeyUriResponderAdapter
    # Returns: {release, os: {arch, name, version}, _links: {self: url}}
    # ==========================================
    @app_server.route("/", methods=["GET"])
    def info():
        auth_error = app_server.require_auth()
        if auth_error:
            return auth_error

        env = EnvironmentConfiguration.get_environment()
        server_config_repo = ServerConfigRepositoryProperties()
        server_config = server_config_repo.get_current_server_config()

        # Build release: info.build.name + "-" + info.build.version
        release = f"{BUILD_NAME}-{BUILD_VERSION}"

        # Build OS info
        os_info = {
            "arch": platform.machine(),
            "name": platform.system(),
            "version": platform.release(),
        }

        # Build _links
        links = {}
        if server_config and server_config.url:
            links["self"] = LinkResource(href=server_config.url).to_dict()

        # Build hostname (Java InfoServerHandler adds hostname)
        try:
            hostname = get_hostname()
        except Exception:
            hostname = ""

        return jsonify({
            "release": release,
            "os": os_info,
            "_links": links,
            "hostname": hostname,
        })

    # ==========================================
    # GET /modules - List all modules with status (requires auth)
    # Java: StatusModulesHandler
    # ==========================================
    @app_server.route("/modules", methods=["GET"])
    def status_modules():
        auth_error = app_server.require_auth()
        if auth_error:
            return auth_error

        manager = ModuleManagerImpl.get_instance()
        modules = manager.get_all()
        statuses = [ModuleStatus.from_module(m).to_dict() for m in modules]
        return jsonify(statuses)

    # ==========================================
    # GET /modules/<release> - Check single module status (requires auth)
    # Java: InstallModuleHandler.getRequest
    # ==========================================
    @app_server.route("/modules/<release>", methods=["GET"])
    def check_module(release):
        auth_error = app_server.require_auth()
        if auth_error:
            return auth_error

        manager = ModuleManagerImpl.get_instance()
        try:
            module = manager.check(release)
            return jsonify(ModuleStatus.from_module(module).to_dict()), 200
        except ModuleNotFoundException as e:
            return jsonify(ErrorInfo(url=request.path, code=404, reason=str(e)).to_dict()), 404

    # ==========================================
    # POST /modules/<release> - Install module (requires auth)
    # Java: InstallModuleHandler.postRequest
    # ==========================================
    @app_server.route("/modules/<release>", methods=["POST"])
    def install_module(release):
        auth_error = app_server.require_auth()
        if auth_error:
            return auth_error

        manager = ModuleManagerImpl.get_instance()

        # Get uploaded file (Java uses NanoFileUpload for multipart)
        upload_meta = None
        if "file" in request.files:
            file = request.files["file"]
            input_stream = file.stream
            upload_meta = {
                "filename": file.filename,
                "content_type": file.content_type,
            }
        else:
            input_stream = request.data

        try:
            manager.create(release, input_stream, upload_meta=upload_meta)
            module = manager.check(release)
            return jsonify(ModuleStatus.from_module(module).to_dict()), 200
        except ModuleExistsException:
            # Java returns existing module status with 409
            module = manager.check(release)
            return jsonify(ModuleStatus.from_module(module).to_dict()), 409
        except ModuleNotFoundException as e:
            return jsonify(ErrorInfo(url=request.path, code=404, reason=str(e)).to_dict()), 404

    # ==========================================
    # DELETE /modules/<release> - Delete/uninstall module (requires auth)
    # Java: InstallModuleHandler.deleteRequest
    # ==========================================
    @app_server.route("/modules/<release>", methods=["DELETE"])
    def delete_module(release):
        auth_error = app_server.require_auth()
        if auth_error:
            return auth_error

        manager = ModuleManagerImpl.get_instance()
        try:
            manager.delete(release)
            return Response(status=200)
        except ModuleNotFoundException as e:
            return jsonify(ErrorInfo(url=request.path, code=404, reason=str(e)).to_dict()), 404

    # ==========================================
    # POST /modules/<release>/start - Start module (requires auth)
    # Java: StartModuleHandler - returns 406 for ModuleIllegalStateException
    # ==========================================
    @app_server.route("/modules/<release>/start", methods=["POST"])
    def start_module(release):
        auth_error = app_server.require_auth()
        if auth_error:
            return auth_error

        manager = ModuleManagerImpl.get_instance()
        try:
            args = request.get_json(silent=True)
            manager.start(release, args)
            module = manager.check(release)
            return jsonify(ModuleStatus.from_module(module).to_dict()), 200
        except ModuleNotFoundException as e:
            return jsonify(ErrorInfo(url=request.path, code=404, reason=str(e)).to_dict()), 404
        except ModuleIllegalStateException:
            # Java returns 406 NOT_ACCEPTABLE with current module status
            module = manager.check(release)
            return jsonify(ModuleStatus.from_module(module).to_dict()), 406

    # ==========================================
    # POST /modules/<release>/stop - Stop module (requires auth)
    # Java: StopModuleHandler - lets ModuleIllegalStateException propagate -> 406
    # ==========================================
    @app_server.route("/modules/<release>/stop", methods=["POST"])
    def stop_module(release):
        auth_error = app_server.require_auth()
        if auth_error:
            return auth_error

        manager = ModuleManagerImpl.get_instance()
        try:
            manager.stop(release)
            module = manager.check(release)
            return jsonify(ModuleStatus.from_module(module).to_dict()), 200
        except ModuleNotFoundException as e:
            return jsonify(ErrorInfo(url=request.path, code=404, reason=str(e)).to_dict()), 404
        except ModuleIllegalStateException:
            # Java returns 406 NOT_ACCEPTABLE
            module = manager.check(release)
            return jsonify(ModuleStatus.from_module(module).to_dict()), 406

    # ==========================================
    # POST /discovery/<release> - Register instance (requires server token auth)
    # Java: DiscoveryHandler.postRequest - returns 202 ACCEPTED
    # ==========================================
    @app_server.route("/discovery/<release>", methods=["POST"])
    def discovery_registry(release):
        auth_error = app_server.require_server_auth()
        if auth_error:
            return auth_error

        data = request.get_json(force=True)
        instance_id = data.get("instanceId", "")
        url = data.get("url", "")

        info = InstanceInfo(release=release, instance_id=instance_id, url=url)
        manager = DiscoveryManagerImpl.get_instance()

        try:
            manager.registry(info)
            return Response(status=202)  # Java returns 202 ACCEPTED
        except InstanceInfoExistsException as e:
            return jsonify(ErrorInfo(url=request.path, code=409, reason=str(e)).to_dict()), 409

    # ==========================================
    # PUT /discovery/<release> - Heartbeat (requires server token auth)
    # Java: DiscoveryHandler.putRequest
    # ==========================================
    @app_server.route("/discovery/<release>", methods=["PUT"])
    def discovery_heartbeat(release):
        auth_error = app_server.require_server_auth()
        if auth_error:
            return auth_error

        data = request.get_json(force=True)
        instance_id = data.get("instanceId", "")
        url = data.get("url", "")

        info = InstanceInfo(release=release, instance_id=instance_id, url=url)
        manager = DiscoveryManagerImpl.get_instance()

        try:
            manager.update(info)
            return Response(status=200)
        except InstanceInfoNotFoundException as e:
            return jsonify(ErrorInfo(url=request.path, code=404, reason=str(e)).to_dict()), 404

    # ==========================================
    # DELETE /discovery/<release>/<instanceId> - Unregister (requires server token auth)
    # Java: DiscoveryHandler.deleteRequest
    # ==========================================
    @app_server.route("/discovery/<release>/<instance_id>", methods=["DELETE"])
    def discovery_unregistry(release, instance_id):
        auth_error = app_server.require_server_auth()
        if auth_error:
            return auth_error

        manager = DiscoveryManagerImpl.get_instance()
        manager.unregistry(release, instance_id)
        return Response(status=200)

    # ==========================================
    # POST /connect - URI schema connection (requires server token auth)
    # Java: MvupdateConnectHandler
    # ==========================================
    @app_server.route("/connect", methods=["POST"])
    def connect():
        auth_error = app_server.require_server_auth()
        if auth_error:
            return auth_error

        data = request.get_json(force=True)
        key_data = data if isinstance(data, dict) else {"id": str(data)}
        key = MvupdateKey.from_json(key_data)

        # Store the key for authentication
        repo = MvupdateKeyRepositoryImpl()
        repo.add_instance(key)

        # Java returns 200 OK with empty text/plain body
        return Response(status=200)

    # ==========================================
    # POST /shutdown - Shutdown server (if enabled)
    # Java: ShutdownHandler
    # ==========================================
    @app_server.route("/shutdown", methods=["POST"])
    def shutdown():
        if not app_server.enable_shutdown:
            return Response(status=405)  # Java returns 405 METHOD_NOT_ALLOWED

        logger.info("Shutdown requested")

        def do_shutdown():
            import time
            time.sleep(0.5)
            import os
            os._exit(0)

        import threading
        thread = threading.Thread(target=do_shutdown, daemon=True)
        thread.start()
        return Response(status=200)
