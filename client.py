from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain.agents import create_agent
from langchain_groq import ChatGroq
from langgraph.checkpoint.memory import InMemorySaver  
from langchain.messages import SystemMessage, HumanMessage


from dotenv import load_dotenv 
load_dotenv()

import asyncio

async def main():
    client = MultiServerMCPClient(
        {
            "math": {
                "command": "python",
                "args": ["servers/math_mcp.py"],
                "transport": "stdio",
            }, 
            "postgres": {
			    "command": "uv",
			    "args": [
				    "run",
				    "postgres-mcp",
				    "--access-mode=unrestricted"
			    ],
			    "env": {
				    "DATABASE_URI": "postgresql://agentic:Anurag2004@localhost:5432/blog"
			    },
			    "transport": "stdio"
		    },
            "my-mcp-server-96a35bfe": {
			    "url": "https://mcp.dice.com/mcp",
			    "transport": "http"
		    }
        }
    )


    import os 
    os.environ["GROQ_API_KEY"] = os.getenv("GROQ_API_KEY")

    tools = await client.get_tools()
    model = ChatGroq(model="openai/gpt-oss-20b")

    # for t in tools:
    #     print(t.name)
    #     print(t.description)
    #     print(t.args_schema)

    agent = create_agent(
        model, 
        tools,
        checkpointer=InMemorySaver()
    )

    config = {
        "configurable": {
            "thread_id": "t1"
        }
    }

    # math_response = await agent.ainvoke(
    #     {"messages": [{
    #         "role": "user",
    #         "content": "what is (43 - 12) * (19 + 34)?"
    #     }]},
    #     config=config
    # )

    # print("Math Response:", math_response['messages'][-1].content)

    # query_response = await agent.ainvoke(
    #     {
    #         "messages": [{
    #             "role": "user",
    #             "content": "Can you define the structure of the table resumes, please describe it."
    #         }]
    #     },
    #     config=config
    # )

    # print("Query Response:", query_response['messages'][-1].content)

    user_prompt = "Find junior software developer roles"

    job_description_search = await agent.ainvoke(
        {
            "messages": [
                SystemMessage(content="From the list of Jobs, don't repeat the previous job post and return only 1 posting each time, and return all details of it properly in json format."),
                HumanMessage(content=user_prompt)
            ]
        },
        config=config
    )

    job_search_result = job_description_search["messages"][-1].content

    print("Search Result: \n", job_search_result)

    system_prompt = """

You are an expert technical recruiter and job description writer.

Your task is to convert raw job listing data into a clean, professional, SEO-optimized job description suitable for a job board or careers page.

The input may contain inconsistent formatting, missing fields, or noisy text. Clean and organize the information without inventing missing details.

Requirements:

* Write clear, professional English.
* Keep the description concise and engaging.
* Maximum length: 150–200 words.
* Do NOT fabricate information. If data is missing, omit it.
* Naturally include relevant keywords such as job title, technologies, and specialization.
* Avoid keyword stuffing.

Output format:

Job Title:
Company:
Location:
Employment Type (if available)

Overview:
Provide a short 2–3 sentence summary describing the role and its impact.

Responsibilities:
• List 3–5 key responsibilities.

Required Skills:
• List main technologies or required skills.

Preferred Qualifications:
• Include only if present in the input data.

Input job data format example:

{
"title": "...",
"company": "...",
"location": "...",
"description": "...",
"skills": [...]
}

Now convert the following raw job data into the structured job description described above.
"""

    job_response = await agent.ainvoke(
        {
            "messages": [
                SystemMessage(
                    content=system_prompt
                ),
                HumanMessage(
                    content=f"Generate the JD for the 2nd job post from {job_search_result}"
                )
            ]
        },
        config=config
    )

    print("Job Description Response:\n", job_response['messages'][-1].content)




asyncio.run(main())