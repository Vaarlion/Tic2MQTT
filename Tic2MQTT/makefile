## Build and commit the site

default: help
.DEFAULT_GOAL := help
SHELL = /bin/bash
mkfile_path := $(abspath $(lastword $(MAKEFILE_LIST)))
current_dir := $(patsubst %/,%,$(dir $(mkfile_path)))


install: create_venv pip_requirements chmod_script install_service inform_todo ## Full install

uninstall: ## Remove everything
	sudo systemctl disable --now tic2mqtt.service
	sudo systemctl reset-failed tic2mqtt.service
	sudo systemctl daemon-reload
	rm -f /etc/systemd/system/tic2mqtt.service
	rm -rf $(current_dir)

create_venv: # Create a python venv in the current directory
	python3 -m venv $(current_dir)/venv --system-site-packages

chmod_script: # Allow execution of the python script
	chmod 0755 $(current_dir)/Tic2MQTT.py
	chmod 0660 $(current_dir)/configurations.ini

pip_requirements: # Install all pip requirement in the venv
	test -d $(current_dir)/venv
	. $(current_dir)/venv/bin/activate; pip install -r ./requirements

install_service: # Simlink the service file in the systemd directory and reload deamon
	test -d /etc/systemd/system
	test -f /etc/systemd/system/tic2mqtt.service || sudo ln -s $(current_dir)/tic2mqtt.service /etc/systemd/system/tic2mqtt.service
	sudo systemctl daemon-reload

inform_todo: # infrome the user of the list of thing still to do manualy
	$(info To finish instalation, please create a system user called tic_user, fill the config file at $(current_dir)/configurations.ini and run `sudo systemctl enable --now tic2mqtt.service`)


help: ## display this message
	@grep -h -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-30s\033[0m %s\n", $$1, $$2}'
