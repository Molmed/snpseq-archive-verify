import argparse
import logging
import logging.config
import yaml
import sys
import os

import archive_verify.handlers as handlers

from aiohttp import web

log = logging.getLogger(__name__)

def setup_routes(app):
    app.router.add_post(app["config"]["base_url"] + r"/{endpoint:(verify|download)}", handlers.verify)
    app.router.add_get(app["config"]["base_url"] + "/status/{job_id}", handlers.status)

def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("-c", "--configroot", help="Path to config root dir", type=str, default="/etc/arteria/archive-verify/")
    args = parser.parse_args()

    if not args.configroot or not os.path.isdir(args.configroot):
        msg = "Configuration required. Please specify a valid path to the config root directory with -c."
        log.error(msg)
        sys.exit(1)

    return args

def load_config(args):
    config_file = os.path.join(args.configroot, "app.yaml")
    logger_file = os.path.join(args.configroot, "logger.yaml")

    try:
        with open(logger_file) as logger:
            logger_conf = yaml.load(logger)
            logging.config.dictConfig(logger_conf)

        with open(config_file) as config:
            return yaml.load(config)
    except Exception as e:
        log.error("Could not parse config file {}".format(e))
        sys.exit(1)

def init_config():
    args = parse_args()
    return load_config(args)

def start():
    conf = init_config()
    log.info("Starting archive-verify-ws on {}...".format(conf["port"]))
    app = web.Application()
    app['config'] = conf
    app.cleanup_ctx.append(handlers.redis_context)
    setup_routes(app)
    web.run_app(app, port=conf["port"])

