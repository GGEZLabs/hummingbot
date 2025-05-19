from decimal import Decimal

import pandas as pd

from hummingbot.connector.connector_base import ConnectorBase


class RiskManagement:
    def __init__(
        self,
        balance_loss_threshold: Decimal,
        starting_balance: pd.DataFrame,
        connector: ConnectorBase,
        base: str,
        quote: str,
        trading_pair: str,
    ):
        self.balance_loss_threshold = balance_loss_threshold
        self.starting_balance = starting_balance
        self.connector = connector
        self.base = base
        self.quote = quote
        self.trading_pair = trading_pair

    def _calculate_quote_base_balance_threshold(self):
        quote_threshold = self.balance_loss_threshold
        mid_price = self.connector.get_mid_price(self.trading_pair)
        base_threshold = quote_threshold / mid_price
        return quote_threshold, base_threshold

    def _get_balance_differences_df(self, current_balance: pd.DataFrame):
        starting_balance = self.starting_balance
        balance_differences_df = pd.DataFrame(
            {
                "Exchange": starting_balance["Exchange"],
                "Asset": starting_balance["Asset"],
                "Starting_Available_Balance": starting_balance["Available Balance"],
                "Starting_Balance": starting_balance["Total Balance"],
                "Current_Available_Balance": current_balance["Available Balance"],
                "Current_Balance": current_balance["Total Balance"],
            }
        )
        balance_differences_df["Difference_Balance"] = (
            balance_differences_df["Current_Balance"] - balance_differences_df["Starting_Balance"]
        )
        balance_differences_df["Difference_Available_Balance"] = (
            balance_differences_df["Current_Available_Balance"] - balance_differences_df["Starting_Available_Balance"]
        )
        return balance_differences_df

    def _check_balance_threshold(self, balance_df, asset, threshold):
        try:
            difference_balance = abs(
                Decimal(balance_df.loc[balance_df["Asset"] == asset, "Difference_Balance"].iloc[0])
            )
            # difference_available_balance = abs(
            #     Decimal(balance_df.loc[balance_df["Asset"] == asset, "Difference_Available_Balance"].iloc[0])
            # )
            return difference_balance > threshold
            # or difference_available_balance > threshold
        except (KeyError, IndexError):
            return False

    def _check_thresholds(self, balance_df, base_threshold, quote_threshold):
        base_condition = self._check_balance_threshold(balance_df, self.base, base_threshold)
        quote_condition = self._check_balance_threshold(balance_df, self.quote, quote_threshold)
        return base_condition, quote_condition

    def is_balance_below_thresholds(self, current_balance: pd.DataFrame) -> tuple[bool, str]:
        quote_threshold, base_threshold = self._calculate_quote_base_balance_threshold()
        balance_differences_df = self._get_balance_differences_df(current_balance)
        number_of_markets = len(balance_differences_df["Exchange"].unique())
        if number_of_markets > 1:
            balance_differences_df = (
                balance_differences_df.groupby("Asset")
                .agg(
                    {
                        "Starting_Available_Balance": "sum",
                        "Starting_Balance": "sum",
                        "Current_Available_Balance": "sum",
                        "Current_Balance": "sum",
                        "Difference_Balance": "sum",
                        "Difference_Available_Balance": "sum",
                    }
                )
                .reset_index()
            )

        base_condition, quote_condition = self._check_thresholds(
            balance_differences_df.round(2), base_threshold, quote_threshold
        )
        is_below_threshold = base_condition or quote_condition
        notification = self._generate_telegram_notification(balance_differences_df, base_condition, quote_condition)
        return is_below_threshold, notification

    def check_balance_returned(self, current_balance: pd.DataFrame) -> bool:
        if current_balance.equals(self.starting_balance):
            return True
        number_of_markets = len(current_balance["Exchange"].unique())
        if number_of_markets > 1:
            current_balance_df_agg = (
                current_balance.groupby("Asset")
                .agg(
                    {
                        "Total Balance": "sum",
                        "Available Balance": "sum",
                    }
                )
                .round(2)
            )
            starting_balance_df_agg = (
                self.starting_balance.groupby("Asset")
                .agg(
                    {
                        "Total Balance": "sum",
                        "Available Balance": "sum",
                    }
                )
                .round(2)
            )
            if current_balance_df_agg.equals(starting_balance_df_agg):
                return True
        return False

    def _generate_telegram_notification(
        self, balance_differences_df: pd.DataFrame, base_condition: bool, quote_condition: bool
    ) -> str:
        notification = ""
        if base_condition or quote_condition:
            notification = "\nWARNING : Balance below threshold."
            if base_condition:
                base_balance = balance_differences_df.loc[balance_differences_df["Asset"] == self.base].iloc[0]
                notification += "\nBase Asset getting below threshold"
                notification += f"\nCurrent Base Balance: {str(base_balance['Current_Balance'])}"
                notification += f"\nDifference Base : {str(base_balance['Difference_Balance'])}"
                notification += (
                    f"\nDifference Base Available Balance : {str(base_balance['Difference_Available_Balance'])}"
                )

            if quote_condition:
                quote_balance = balance_differences_df.loc[balance_differences_df["Asset"] == self.quote].iloc[0]
                notification += "\nQuote Asset getting below threshold"
                notification += f"\nCurrent Quote Balance: {str(quote_balance['Current_Balance'])}"
                notification += f"\nDifference Quote : {str(quote_balance['Difference_Balance'])}"
                notification += (
                    f"\nDifference Quote Available Balance : {str(quote_balance['Difference_Available_Balance'])}"
                )

        return notification
