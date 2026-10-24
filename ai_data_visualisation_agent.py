"""
AI Data Visualization Agent
===========================
An autonomous data science and visualization agent powered by open-source LLMs 
(via Together AI) and isolated cloud sandboxes (via E2B Code Interpreter).

Author: Vaibhav Kakad
License: MIT
"""

import os
import re
import sys
import io
import base64
import contextlib
import warnings
from typing import Optional, List, Any, Tuple
from io import BytesIO

from PIL import Image
import streamlit as st
import pandas as pd
from dotenv import load_dotenv
from together import Together
from e2b_code_interpreter import Sandbox

# Load environment variables if available
load_dotenv()

# Filter specific pydantic warnings
warnings.filterwarnings("ignore", category=UserWarning, module="pydantic")

# Regex pattern for capturing Python code blocks
CODE_PATTERN = re.compile(r"```(?:python|py)?\s*\n?(.*?)\n?```", re.DOTALL)


def code_interpret(e2b_code_interpreter: Sandbox, code: str) -> Optional[List[Any]]:
    """Executes Python code safely inside an isolated E2B Sandbox environment."""
    with st.spinner("Executing analytical code inside secure E2B sandbox..."):
        stdout_capture = io.StringIO()
        stderr_capture = io.StringIO()

        with contextlib.redirect_stdout(stdout_capture), contextlib.redirect_stderr(stderr_capture):
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                exec_result = e2b_code_interpreter.run_code(code)

        if stderr_capture.getvalue():
            print("[Code Interpreter Warnings/Errors]", file=sys.stderr)
            print(stderr_capture.getvalue(), file=sys.stderr)

        if stdout_capture.getvalue():
            print("[Code Interpreter Output]", file=sys.stdout)
            print(stdout_capture.getvalue(), file=sys.stdout)

        if exec_result.error:
            print(f"[Code Interpreter ERROR] {exec_result.error}", file=sys.stderr)
            st.error(f"Sandbox Execution Error: {exec_result.error.name} - {exec_result.error.value}")
            return None
            
        return exec_result.results


def match_code_blocks(llm_response: str) -> str:
    """Extracts executable Python code block from LLM markdown response."""
    match = CODE_PATTERN.search(llm_response)
    if match:
        return match.group(1).strip()
    return ""


def chat_with_llm(
    e2b_code_interpreter: Sandbox, 
    user_message: str, 
    dataset_path: str
) -> Tuple[Optional[List[Any]], str, str]:
    """Generates Python code using Together AI and executes it in the E2B sandbox."""
    system_prompt = f"""You are an expert Python data scientist and data visualization engineer.
You are given a dataset file located at '{dataset_path}' and the user's analytical query.
Analyze the dataset and answer the user's query by generating complete, bug-free Python code.

GUIDELINES:
1. Always load the dataset from variable: '{dataset_path}'.
2. Create clear, aesthetically pleasing visualizations (using matplotlib, seaborn, or plotly).
3. Always wrap your executable Python code inside a ```python ``` block.
4. Clean, summarize, and display results cleanly.
"""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_message},
    ]

    with st.spinner("Generating analytical code with Together AI model..."):
        client = Together(api_key=st.session_state.together_api_key)
        response = client.chat.completions.create(
            model=st.session_state.model_name,
            messages=messages,
        )

        response_message = response.choices[0].message
        python_code = match_code_blocks(response_message.content)

        if python_code:
            code_interpreter_results = code_interpret(e2b_code_interpreter, python_code)
            return code_interpreter_results, response_message.content, python_code
        else:
            st.warning("No executable Python code block found in the model's response.")
            return None, response_message.content, ""


def upload_dataset(code_interpreter: Sandbox, file_name: str, file_bytes: bytes) -> str:
    """Uploads dataset bytes to the E2B sandbox environment."""
    dataset_path = f"./{file_name}"
    try:
        code_interpreter.files.write(dataset_path, file_bytes)
        return dataset_path
    except Exception as error:
        st.error(f"Error during sandbox file upload: {error}")
        raise error


def main():
    """Main Streamlit application."""
    st.set_page_config(
        page_title="AI Data Visualization Agent",
        page_icon="📊",
        layout="wide",
        initial_sidebar_state="expanded"
    )

    st.title("📊 AI Data Visualization Agent")
    st.markdown(
        "Transform natural language queries into automated statistical analyses and "
        "production-grade visualizations using **Open-Source LLMs** and **E2B Secure Sandboxes**."
    )

    # Initialize session state variables with environment variable fallbacks
    if "together_api_key" not in st.session_state:
        st.session_state.together_api_key = os.getenv("TOGETHER_API_KEY", "")
    if "e2b_api_key" not in st.session_state:
        st.session_state.e2b_api_key = os.getenv("E2B_API_KEY", "")
    if "model_name" not in st.session_state:
        st.session_state.model_name = "meta-llama/Meta-Llama-3.1-405B-Instruct-Turbo"

    # Sidebar: API Keys and Model Configuration
    with st.sidebar:
        st.header("⚙️ Configuration")
        
        together_key_input = st.text_input(
            "Together AI API Key",
            value=st.session_state.together_api_key,
            type="password",
            help="Get $1 free credit at api.together.ai"
        )
        if together_key_input:
            st.session_state.together_api_key = together_key_input

        st.caption("🔑 [Get Together AI Key](https://api.together.ai/signin)")

        e2b_key_input = st.text_input(
            "E2B API Key",
            value=st.session_state.e2b_api_key,
            type="password",
            help="Sandbox execution platform at e2b.dev"
        )
        if e2b_key_input:
            st.session_state.e2b_api_key = e2b_key_input

        st.caption("🔑 [Get E2B API Key](https://e2b.dev)")

        st.markdown("---")
        st.subheader("🧠 Model Selection")
        
        model_options = {
            "Meta-Llama 3.1 405B (Flagship)": "meta-llama/Meta-Llama-3.1-405B-Instruct-Turbo",
            "DeepSeek V3 (Reasoning & Code)": "deepseek-ai/DeepSeek-V3",
            "Meta-Llama 3.3 70B (Fast & Accurate)": "meta-llama/Llama-3.3-70B-Instruct-Turbo",
            "Qwen 2.5 7B (Lightweight)": "Qwen/Qwen2.5-7B-Instruct-Turbo"
        }
        
        selected_label = st.selectbox(
            "Select LLM Backbone",
            options=list(model_options.keys()),
            index=0
        )
        st.session_state.model_name = model_options[selected_label]

        st.markdown("---")
        st.markdown(
            "**Architecture:**\n"
            "- 🧠 Open-Source LLM via Together AI\n"
            "- 🛡️ Isolated execution in E2B Sandbox\n"
            "- 📈 Matplotlib / Seaborn / Plotly rendering"
        )

    # Main Area: Dataset Selection & Upload
    col1, col2 = st.columns([2, 1])
    with col1:
        data_source = st.radio(
            "Choose Data Source:",
            ["📁 Upload CSV File", "📊 Load Sample Dataset (Supermarket Retail Sales)"],
            horizontal=True
        )

    df: Optional[pd.DataFrame] = None
    file_name: str = ""
    file_bytes: Optional[bytes] = None

    if data_source == "📁 Upload CSV File":
        uploaded_file = st.file_uploader("Upload a CSV file for analysis", type=["csv"])
        if uploaded_file is not None:
            file_name = uploaded_file.name
            file_bytes = uploaded_file.getvalue()
            df = pd.read_csv(BytesIO(file_bytes))
    else:
        sample_path = os.path.join(os.path.dirname(__file__), "data", "sample_sales_data.csv")
        if os.path.exists(sample_path):
            file_name = "sample_sales_data.csv"
            with open(sample_path, "rb") as f:
                file_bytes = f.read()
            df = pd.read_csv(sample_path)
            st.info("Loaded sample dataset: Supermarket Retail Sales (150 records)")
        else:
            st.warning("Sample dataset not found locally. Please upload a CSV file.")

    if df is not None and file_bytes is not None:
        # Dataset Summary Metrics
        st.subheader("📋 Dataset Overview")
        m1, m2, m3 = st.columns(3)
        m1.metric("Total Rows", f"{len(df):,}")
        m2.metric("Total Columns", len(df.columns))
        m3.metric("Memory Usage", f"{df.memory_usage().sum() / 1024:.1f} KB")

        # Preview Toggle
        with st.expander("👁️ Preview Dataset Table", expanded=False):
            show_all = st.checkbox("Show all rows", value=False)
            st.dataframe(df if show_all else df.head(10), use_container_width=True)

        st.markdown("---")
        st.subheader("💬 Ask Questions & Generate Visualizations")

        # Quick Example Prompts
        st.caption("💡 Quick prompts:")
        example_cols = st.columns(3)
        default_query = "Can you compare the average gross income across different product lines and visualize the breakdown?"
        
        if example_cols[0].button("📊 Gross Income by Product"):
            st.session_state.current_query = "Can you compare the average gross income across different product lines with a bar chart?"
        if example_cols[1].button("📈 Sales Trend by Date"):
            st.session_state.current_query = "Plot the daily total sales trend over time with a line plot."
        if example_cols[2].button("⭐ Ratings vs Total Spend"):
            st.session_state.current_query = "Show a scatter plot of Customer Ratings vs Total Spend grouped by Customer Type."

        query_value = st.session_state.get("current_query", default_query)
        user_query = st.text_area("Analytical Query:", value=query_value, height=90)

        if st.button("🚀 Run Analysis & Visualize", type="primary"):
            if not st.session_state.together_api_key or not st.session_state.e2b_api_key:
                st.error("Please configure both Together AI and E2B API keys in the sidebar.")
            else:
                try:
                    with Sandbox(api_key=st.session_state.e2b_api_key) as code_interpreter:
                        # Upload dataset to sandbox
                        dataset_path = upload_dataset(code_interpreter, file_name, file_bytes)

                        # Run LLM + Sandbox analysis
                        code_results, llm_response, generated_code = chat_with_llm(
                            code_interpreter, 
                            user_query, 
                            dataset_path
                        )

                        # Display Natural Language Interpretation
                        st.subheader("💡 Analytical Summary")
                        st.markdown(llm_response)

                        # Display Visualizations & Artifacts
                        if code_results:
                            st.subheader("📊 Generated Visualizations")
                            for result in code_results:
                                if hasattr(result, "png") and result.png:
                                    png_bytes = base64.b64decode(result.png)
                                    image = Image.open(BytesIO(png_bytes))
                                    st.image(image, caption="Generated Visual Output", use_container_width=True)
                                elif hasattr(result, "figure"):
                                    st.pyplot(result.figure)
                                elif hasattr(result, "show"):
                                    st.plotly_chart(result, use_container_width=True)
                                elif isinstance(result, (pd.DataFrame, pd.Series)):
                                    st.dataframe(result, use_container_width=True)
                                else:
                                    st.write(result)

                        # Inspect Python Code Block
                        if generated_code:
                            with st.expander("🔍 Inspect Generated Python Code", expanded=False):
                                st.code(generated_code, language="python")

                except Exception as e:
                    st.error(f"Analysis encountered an error: {str(e)}")


if __name__ == "__main__":
    main()