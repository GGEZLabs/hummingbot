from pydantic import Field

from hummingbot.client.config.config_data_types import ClientFieldData
from scripts.utils.custom_volume_pumper_config import CustomVolumePumperConfig


class TwoAccountsVolumePumperConfig(CustomVolumePumperConfig):
    """
    This is a configuration class for a volume pumper bot that trades on two different accounts.
    It inherits from the CustomVolumePumperConfig class and adds additional fields specific to the two-account setup.
    """

    # The account ID of the second account to be used for trading
    second_exchange: str = Field(
        "coinstore_2",
        client_data=ClientFieldData(
            prompt_on_new=True,
            prompt=lambda mi: "second Exchange where the bot will trade , it should be the same exchange as the first one but with different instance",
        ),
    )
