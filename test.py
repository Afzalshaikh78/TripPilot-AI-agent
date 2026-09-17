
from backend import run_travel_agent
from mcp_client import get_all_tools
import asyncio



# response = tavily_search("best hotels in india")
# print(response)


# user_input = input("Enter travel request: ")

# response = run_travel_agent(
#     user_input=user_input,
#     thread_id="test_user"
# )


# print("\nFINAL RESPONSE:\n")
# print(response["answer"])

if __name__ == "__main__":
    asyncio.run(get_all_tools())