import os
import logging
import json
from dotenv import load_dotenv
from agents import Agent, Runner, function_tool  # Only import what you need
import stripe
from typing_extensions import TypedDict, Any
import asyncio
# Load environment variables from .env file
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Set Stripe API key from environment variables
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")

@function_tool
def get_phone_logs(phone_number: str) -> list:
    """
    Return a list of phone call records for the given phone number.
    Each record might include call timestamps, durations, notes, 
    and an associated order_id if applicable.
    """
    phone_logs = [
        {
            "phone_number": "+15551234567",
            "timestamp": "2023-03-14 15:24:00",
            "duration_minutes": 5,
            "notes": "Asked about status of order #1121",
            "order_id": 1121
        },
        {
            "phone_number": "+15551234567",
            "timestamp": "2023-02-28 10:10:00",
            "duration_minutes": 7,
            "notes": "Requested refund for order #1121, I told him we were unable to refund the order because it was final sale",
            "order_id": 1121
        },
        {
            "phone_number": "+15559876543",
            "timestamp": "2023-01-05 09:00:00",
            "duration_minutes": 2,
            "notes": "General inquiry; no specific order mentioned",
            "order_id": None
        },
    ]
    return [
        log for log in phone_logs if log["phone_number"] == phone_number
    ]


@function_tool
def get_order(order_id: int) -> str:
    """
    Retrieve an order by ID from a predefined list of orders.
    Returns the corresponding order object or 'No order found'.
    """
    orders = [
        {
            "order_id": 1234,
            "fulfillment_details": "not_shipped"
        },
        {
            "order_id": 9101,
            "fulfillment_details": "shipped",
            "tracking_info": {
                "carrier": "FedEx",
                "tracking_number": "123456789012"
            },
            "delivery_status": "out for delivery"
        },
        {
            "order_id": 1121,
            "fulfillment_details": "delivered",
            "customer_id": "cus_PZ1234567890",
            "customer_phone": "+15551234567",
            "order_date": "2023-01-01",
            "customer_email": "customer1@example.com",
            "tracking_info": {
                "carrier": "UPS",
                "tracking_number": "1Z999AA10123456784",
                "delivery_status": "delivered"
            },
            "shipping_address": {
                "zip": "10001"
            },
            "tos_acceptance": {
                "date": "2023-01-01",
                "ip": "192.168.1.1"
            }
        }
    ]
    for order in orders:
        if order["order_id"] == order_id:
            return order
    return "No order found"


@function_tool
def get_emails(email: str) -> list:
    """
    Return a list of email records for the given email address.
    """
    emails = [
        {
            "email": "customer1@example.com",
            "subject": "Order #1121",
            "body": "Hey, I know you don't accept refunds but the sneakers don't fit and I'd like a refund"
        },
        {
            "email": "customer2@example.com",
            "subject": "Inquiry about product availability",
            "body": "Hello, I wanted to check if the new model of the smartphone is available in stock."
        },
        {
            "email": "customer3@example.com",
            "subject": "Feedback on recent purchase",
            "body": "Hi, I recently purchased a laptop from your store and I am very satisfied with the product. Keep up the good work!"
        }
    ]
    return [email_data for email_data in emails if email_data["email"] == email]


@function_tool
async def retrieve_payment_intent(payment_intent_id: str) -> dict:
    """
    Retrieve a Stripe payment intent by ID.
    Returns the payment intent object on success or an empty dictionary on failure.
    """
    try:
        return stripe.PaymentIntent.retrieve(payment_intent_id)
    except stripe.error.StripeError as e:
        logger.error(f"Stripe error occurred while retrieving payment intent: {e}")
        return {}

@function_tool
async def close_dispute(dispute_id: str) -> dict:
    """
    Close a Stripe dispute by ID. 
    Returns the dispute object on success or an empty dictionary on failure.
    """
    try:
        return stripe.Dispute.close(dispute_id)
    except stripe.error.StripeError as e:
        logger.error(f"Stripe error occurred while closing dispute: {e}")
        return {}



investigator_agent = Agent(
    name="Dispute Intake Agent",
    instructions=(
        "As a dispute investigator, please compile the following details in your final output:\n\n"
        "Dispute Details:\n"
        "- Dispute ID\n"
        "- Amount\n"
        "- Reason for Dispute\n"
        "- Card Brand\n\n"
        "Payment & Order Details:\n"
        "- Fulfillment status of the order\n"
        "- Shipping carrier and tracking number\n"
        "- Confirmation of TOS acceptance\n\n"
        "Email and Phone Records:\n"
        "- Any relevant email threads (include the full body text)\n"
        "- Any relevant phone logs\n"
    ),
    model="o3-mini",
    tools=[get_emails, get_phone_logs]
)


accept_dispute_agent = Agent(
    name="Accept Dispute Agent",
    instructions=(
        "You are an agent responsible for accepting disputes. Please do the following:\n"
        "1. Use the provided dispute ID to close the dispute.\n"
        "2. Provide a short explanation of why the dispute is being accepted.\n"
        "3. Reference any relevant order details (e.g., unfulfilled order, etc.) retrieved from the database.\n\n"
        "Then, produce your final output in this exact format:\n\n"
        "Dispute Details:\n"
        "- Dispute ID\n"
        "- Amount\n"
        "- Reason for Dispute\n\n"
        "Order Details:\n"
        "- Fulfillment status of the order\n\n"
        "Reasoning for closing the dispute\n"
    ),
    model="gpt-4o",
    tools=[close_dispute]
)

triage_agent = Agent(
    name="Triage Agent",
    instructions=(
        "Please do the following:\n"
        "1. Find the order ID from the payment intent's metadata.\n"
        "2. Retrieve detailed information about the order (e.g., shipping status).\n"
        "3. If the order has shipped, escalate this dispute to the investigator agent.\n"
        "4. If the order has not shipped, accept the dispute.\n"
    ),
    model="gpt-4o",
    tools=[retrieve_payment_intent, get_order],
    handoffs=[accept_dispute_agent, investigator_agent],
)
async def process_dispute(payment_intent_id, triage_agent):
    """Retrieve and process dispute data for a given PaymentIntent."""
    disputes_list = stripe.Dispute.list(payment_intent=payment_intent_id)
    if not disputes_list.data:
        logger.warning("No dispute data found for PaymentIntent: %s", payment_intent_id)
        return None
    
    dispute_data = disputes_list.data[0]
    
    relevant_data = {
        "dispute_id": dispute_data.get("id"),
        "amount": dispute_data.get("amount"),
        "due_by": dispute_data.get("evidence_details", {}).get("due_by"),
        "payment_intent": dispute_data.get("payment_intent"),
        "reason": dispute_data.get("reason"),
        "status": dispute_data.get("status"),
        "card_brand": dispute_data.get("payment_method_details", {}).get("card", {}).get("brand")
    }
    
    event_str = json.dumps(relevant_data)
    # Pass the dispute data to the triage agent
    result = await Runner.run(triage_agent, input=event_str)
    logger.info("WORKFLOW RESULT: %s", result.final_output)
    
    return relevant_data, result.final_output


if __name__ == "__main__":
 
    
    payment = stripe.PaymentIntent.create(
        amount=2000,
        currency="usd",
        payment_method="pm_card_createDisputeProductNotReceived",
        confirm=True,
        metadata={"order_id": "1234"},
        off_session=True,
        automatic_payment_methods={"enabled": True},
    )
    relevant_data, triage_result = asyncio.run(process_dispute(payment.id, triage_agent))
    print("Relevant Data:", relevant_data)
    print("Triage Result:", triage_result)
    # Run the main function
    