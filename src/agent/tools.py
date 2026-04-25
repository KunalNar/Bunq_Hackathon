"""
tools.py — Anthropic tool schemas for every capability the agent has.

Each entry in TOOL_DEFINITIONS is passed directly to the Claude API.
The `description` field is the model's primary signal for *when* to use
the tool — write them like you're writing documentation for a smart junior
analyst who doesn't know the codebase.

Adding a new tool? Do it here AND in handlers.py. The two files stay in sync.
"""

TOOL_DEFINITIONS = [
    {
        "name": "get_balance",
        "description": (
            "Returns the current EUR balance of the user's primary bunq account. "
            "Use this first whenever the user asks about money, spending, or affordability. "
            "Do NOT call this repeatedly in one turn."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "list_transactions",
        "description": (
            "Returns recent transactions from the user's bunq account, ordered newest-first. "
            "Each transaction includes: id, date, merchant, amount_eur (negative = spend, "
            "positive = income), description, and category. "
            "Use category_filter to narrow results, e.g. 'food' or 'transport'. "
            "Use limit to control how many to return (default 10, max 50)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "description": "Number of transactions to return (1–50). Default 10.",
                    "minimum": 1,
                    "maximum": 50,
                },
                "category_filter": {
                    "type": "string",
                    "description": "Only return transactions in this category.",
                    "enum": ["food", "transport", "rent", "entertainment", "utilities", "other"],
                },
            },
            "required": [],
        },
    },
    {
        "name": "lookup_contact",
        "description": (
            "Looks up a contact by first name or full name and returns their IBAN and email. "
            "ALWAYS call this before create_payment when the user says a person's name — "
            "you need the IBAN to make a payment. Returns a list of matches; if multiple "
            "contacts share the name, show the options and ask the user to confirm which one."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "First name or full name of the contact to look up.",
                },
            },
            "required": ["name"],
        },
    },
    {
        "name": "create_payment",
        "description": (
            "Transfers money from the user's bunq account to another IBAN. "
            "IMPORTANT SAFETY RULE: Always confirm with the user before calling this — "
            "repeat back the recipient, amount, and description, and wait for explicit 'yes'. "
            "Never auto-initiate payments without confirmation."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "to_iban": {
                    "type": "string",
                    "description": "Recipient IBAN (e.g. NL91ABNA0417164300).",
                },
                "to_name": {
                    "type": "string",
                    "description": (
                        "Recipient's full name (required by bunq). Use the name "
                        "returned by lookup_contact, or the name the user gave you."
                    ),
                },
                "amount_eur": {
                    "type": "number",
                    "description": "Amount in EUR (positive number, e.g. 25.50).",
                    "exclusiveMinimum": 0,
                },
                "description": {
                    "type": "string",
                    "description": "Payment description visible to both parties (max 140 chars).",
                },
            },
            "required": ["to_iban", "to_name", "amount_eur", "description"],
        },
    },
    {
        "name": "create_request_inquiry",
        "description": (
            "Sends a payment request to someone by email — they get a link to pay the user back. "
            "Great for splitting bills after parsing a receipt. "
            "Use this (not create_payment) when the user wants to *collect* money. "
            "Still confirm amount and recipient before calling."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "to_email": {
                    "type": "string",
                    "description": "Recipient's email address.",
                },
                "amount_eur": {
                    "type": "number",
                    "description": "Amount to request in EUR.",
                    "exclusiveMinimum": 0,
                },
                "description": {
                    "type": "string",
                    "description": "What the request is for (shown to the recipient).",
                },
            },
            "required": ["to_email", "amount_eur", "description"],
        },
    },
    {
        "name": "categorize_transaction",
        "description": (
            "Labels an existing transaction with a spending category. "
            "Call this after list_transactions when the user wants to organise their spending "
            "or when a transaction's auto-category is wrong. "
            "Use exactly one of the enum values."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "transaction_id": {
                    "type": "string",
                    "description": "The transaction ID returned by list_transactions.",
                },
                "category": {
                    "type": "string",
                    "enum": ["food", "transport", "rent", "entertainment", "utilities", "other"],
                    "description": "The spending category to assign.",
                },
            },
            "required": ["transaction_id", "category"],
        },
    },
    {
        "name": "list_savings_goals",
        "description": (
            "Returns all savings jars (sub-accounts) on the user's bunq account, "
            "including the jar name, current balance, savings target (if set), "
            "and how much is still needed to reach the goal. "
            "Use this when the user asks about their savings, funds, jars, or goals."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "top_up_savings_goal",
        "description": (
            "Moves money from the user's main account into one of their savings jars. "
            "Use this when the user wants to add money to a savings goal or fund by name. "
            "Always call list_savings_goals first to confirm the jar exists and show the "
            "current balance. Confirm the jar name, amount, and new balance before calling this."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "jar_name": {
                    "type": "string",
                    "description": "Name of the savings jar to top up (e.g. 'Holiday Fund').",
                },
                "amount_eur": {
                    "type": "number",
                    "description": "Amount in EUR to move into the jar (must be positive).",
                    "exclusiveMinimum": 0,
                },
            },
            "required": ["jar_name", "amount_eur"],
        },
    },
    {
        "name": "create_savings_goal",
        "description": (
            "Creates a new bunq sub-account (savings jar) with a name and optional EUR target. "
            "Use this when the user wants to set aside money for a specific goal "
            "(e.g. 'holiday fund', 'new laptop'). "
            "Do NOT use this for regular payments — this creates an account, not a transfer."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Display name for the savings jar (e.g. 'Holiday 2026').",
                },
                "target_eur": {
                    "type": "number",
                    "description": "Optional savings target in EUR.",
                    "exclusiveMinimum": 0,
                },
            },
            "required": ["name"],
        },
    },
    {
        "name": "parse_receipt",
        "description": (
            "Extracts structured data from a receipt image using computer vision. "
            "Returns: merchant, total, currency, date, line_items[], category_guess. "
            "Call this when the user uploads or mentions a receipt. "
            "The image must be provided as a base64-encoded string."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "image_base64": {
                    "type": "string",
                    "description": "Base64-encoded receipt image (JPEG or PNG).",
                },
            },
            "required": ["image_base64"],
        },
    },
    {
        "name": "log_action",
        "description": (
            "Writes an audit log entry describing an action just taken. "
            "ALWAYS call this after any money-moving action (payment, request, savings creation). "
            "Do NOT call this for read-only operations (balance check, listing transactions)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "action_description": {
                    "type": "string",
                    "description": "One-sentence human-readable summary of what was done.",
                },
            },
            "required": ["action_description"],
        },
    },
]
