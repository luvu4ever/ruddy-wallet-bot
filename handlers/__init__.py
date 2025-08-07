# handlers/__init__.py
from .main_handlers import (
    start,
    handle_message,
    savings_command,
    edit_savings_command,
    category_command,
    help_command,
    monthly_summary,
    list_expenses_command
)

from .wishlist_handlers import (
    wishlist_add_command,
    wishlist_view_command,
    wishlist_remove_command,
    get_wishlist_priority_sums,
    get_wishlist_priority1_sum  # Backward compatibility
)

from .subscription_handlers import (
    subscription_add_command,
    subscription_list_command,
    subscription_remove_command
)

from .budget_handlers import (
    budget_command,
    budget_list_command,
    calculate_remaining_budget,
    get_total_budget
)

from .income_handlers import (
    income_command,
    calculate_income_by_type,
    calculate_expenses_by_income_type
)

from .account_handlers import (
    account_command,
    account_edit_command
)

__all__ = [
    # Main handlers
    "start",
    "handle_message", 
    "savings_command",
    "edit_savings_command",
    "category_command",
    "help_command",
    "monthly_summary",
    "list_expenses_command",
    
    # Wishlist handlers
    "wishlist_add_command",
    "wishlist_view_command", 
    "wishlist_remove_command",
    "get_wishlist_priority_sums",
    "get_wishlist_priority1_sum",  # Backward compatibility
    
    # Subscription handlers
    "subscription_add_command",
    "subscription_list_command",
    "subscription_remove_command",
    
    # Budget handlers
    "budget_command",
    "budget_list_command",
    "calculate_remaining_budget",
    "get_total_budget",
    
    # Income handlers
    "income_command",
    "calculate_income_by_type",
    "calculate_expenses_by_income_type",
    
    # Account handlers
    "account_command",
    "account_edit_command"
]