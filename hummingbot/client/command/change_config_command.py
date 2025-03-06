import logging

from hummingbot.client.config.config_helpers import read_yml_file, save_yml_from_dict
from hummingbot.client.settings import SCRIPT_STRATEGY_CONF_DIR_PATH
from hummingbot.core.utils.async_utils import safe_ensure_future

logger = logging.getLogger(__name__)


class ChangeConfigCommand:

    def change_script_config(
        self,  # type: HummingbotApplication
        raw_command: str,
    ) -> bool:
        commands = raw_command.split(" ")
        command = commands[0]
        if command == "change_script_config":
            safe_ensure_future(self.change_config(commands), loop=self.ev_loop)
            return True
        else:
            return False

    async def change_config(self, commands: list):

        if not self.is_valid_commands(commands):
            return

        file_name = commands[1]
        try:
            strategy_path = SCRIPT_STRATEGY_CONF_DIR_PATH / file_name
            config_map = read_yml_file(strategy_path)

            key_value_inputs = commands[2:]
            for i in range(0, len(key_value_inputs), 2):
                key = key_value_inputs[i]
                value = key_value_inputs[i + 1]
                config_map[key] = self.parse_value(value)

            await save_yml_from_dict(strategy_path, config_map)
            self.notify(f"{file_name}Config File updated successfully.\n{config_map}")

        except FileNotFoundError:
            logger.error("Error reading YAML file", exc_info=True)
            self.notify(f"Invalid File Name,\nFile {file_name} not found.")

        except Exception as e:
            logger.error("Error change_config command", exc_info=True)
            self.notify(str(e))

    def is_valid_commands(self, commands):
        errors = []

        if len(commands) < 4:
            errors.append("Invalid command.")
            errors.append("Please provide the file name followed by key-value pairs.")
            errors.append("Example: change_script_config <file_name> <key1> <value1> <key2> <value2> ...")

        if len(commands) > 12:
            errors.append("Error: You can only provide up to 5 key-value pairs.")

        if len(commands) > 2 and (len(commands) - 2) % 2 != 0:
            errors.append("Error: You must provide an even number of key-value pairs.")

        if errors:
            if len(commands) > 1:
                available_config_keys = self.get_available_config_keys(commands[1])
                errors.append(f"Available keys: {', '.join(available_config_keys)}")

            self.notify("\n".join(errors))
            return False

        return True

    def parse_value(self, value: str):
        parsed_value = None
        if value.lower() == "true":
            parsed_value = True
        elif value.lower() == "false":
            parsed_value = False
        elif "." in value:
            try:
                parsed_value = float(value)
            except ValueError:
                pass
        else:
            try:
                parsed_value = int(value)
            except ValueError:
                pass

        return parsed_value if parsed_value is not None else value

    def get_available_config_keys(self, file_name: str) -> list:
        try:
            strategy_path = SCRIPT_STRATEGY_CONF_DIR_PATH / file_name
            config_map = read_yml_file(strategy_path)
            return config_map.keys()
        except FileNotFoundError:
            logger.error("Error reading YAML file", exc_info=True)
            self.notify(f"Invalid File Name,\nFile {file_name} not found.")
        except Exception as e:
            logger.error("Error change_config command", exc_info=True)
            self.notify(str(e))

        return []


# change_script_config conf_cex_to_dex_lp_price_1.yml key1 0.1 key2 1 key3 True key4 0.0 key5 value5 key6 value6 key7 value7 key8 value8 key9 value9 key10 value10
# change_script_config conf_custom_volume_pumper_1.yml max_random_delay 20 delay_order_time 20 order_lower_amount 100 order_upper_amount 500
