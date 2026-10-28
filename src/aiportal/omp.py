"""omp's custom providers, which it only reads from its models.yml.

Unlike opencode, omp can't be given a separate config file, so the launchers add or
update their own providers in models.yml and leave everything else in it as is.
Secrets stay out of the file: a provider's apiKey names an environment variable,
which omp reads.
"""
import json
import os
import tempfile


def models_path():
    agent_dir = os.environ.get("PI_CODING_AGENT_DIR") or os.path.join(
        os.environ.get("PI_CONFIG_DIR") or os.path.expanduser("~/.omp"), "agent")
    for name in ("models.yml", "models.yaml"):
        if os.path.exists(os.path.join(agent_dir, name)):
            return os.path.join(agent_dir, name)
    return os.path.join(agent_dir, "models.yml")


def update_providers(wanted):
    """Add or update the given providers in models.yml; returns its path."""
    from ruamel.yaml import YAML
    yaml = YAML()
    yaml.indent(mapping=2, sequence=4, offset=2)
    path = models_path()
    config = {}
    if os.path.exists(path):
        with open(path) as f:
            config = yaml.load(f) or {}
    # A "providers:" key with nothing under it loads as None
    providers = config.get("providers") or {}
    config["providers"] = providers
    if all(json.dumps(providers.get(k), sort_keys=True) == json.dumps(v, sort_keys=True) for k, v in wanted.items()):
        return path
    providers.update(wanted)
    # Write a new file and swap it in, so a launch on another machine sharing this
    # home directory never reads it half-written (and drops the providers it lacks)
    target = os.path.realpath(path)  # keep a symlinked models.yml a symlink
    os.makedirs(os.path.dirname(target), mode=0o700, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(target), prefix=".models.yml.")
    try:
        with os.fdopen(fd, "w") as f:
            yaml.dump(config, f)
        os.replace(tmp, target)
    except BaseException:
        os.unlink(tmp)
        raise
    print(f"Updated the {', '.join(wanted)} provider(s) in {path}")
    return path
