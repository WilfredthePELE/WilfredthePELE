# socialai_dashboard.py
import streamlit as st
import os
import base64
import hashlib
import re
import requests
from langchain.chains import ConversationChain
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.prompts import PromptTemplate
import uuid
from datetime import datetime
from langchain.memory import ConversationBufferMemory  # Added import

# Initialize session state
def init_session_state():
    if 'connections' not in st.session_state:
        st.session_state.connections = {}
    if 'user_info' not in st.session_state:
        st.session_state.user_info = {}
    if 'chat_history' not in st.session_state:
        st.session_state.chat_history = []
    if 'session_id' not in st.session_state:
        st.session_state.session_id = str(uuid.uuid4())
    if 'memory_type' not in st.session_state:
        st.session_state.memory_type = "Buffer"
    if 'business_info' not in st.session_state:
        st.session_state.business_info = {
            'name': '',
            'logo': None,
            'color': '#8B5CF6'  # Purple accent
        }

init_session_state()

st.image("logo33.png", width=99)

# --- Configuration ---
GOOGLE_API_KEY = "YOUR_GOOGLE_API_KEY"  # Replace with your key

PLATFORMS = {
    "Facebook": {
        "client_id": "1423783978963836",
        "client_secret": "4e21568eda2eb3031efdd16a829f0c83",
        "authorize_url": "https://www.facebook.com/v19.0/dialog/oauth",
        "token_url": "https://graph.facebook.com/v19.0/oauth/access_token",
        "userinfo_url": "https://graph.facebook.com/me",
        "scope": "pages_manage_posts,pages_read_engagement",
        "icon_path": "facebook.png"
    },
    "Twitter": {
        "client_id": "1058767741572792320-o9pxvoLMlrJsIDF8ZgY18NNsnRrJkR",
        "client_secret": "YOUR_TWITTER_CLIENT_SECRET",
        "authorize_url": "https://twitter.com/i/oauth2/authorize",
        "token_url": "https://api.twitter.com/2/oauth2/token",
        "userinfo_url": "https://api.twitter.com/2/users/me",
        "scope": "tweet.read tweet.write users.read offline.access",
        "icon_path": "x.png"
    },
    "Instagram": {
        "client_id": "1423783978963836",
        "client_secret": "4e21568eda2eb3031efdd16a829f0c83",
        "authorize_url": "https://api.instagram.com/oauth/authorize",
        "token_url": "https://api.instagram.com/oauth/access_token",
        "userinfo_url": "https://graph.instagram.com/me",
        "scope": "user_profile,user_media",
        "icon_path": "instagram.png"
    }
}

REDIRECT_URI = "http://localhost:8501/"

# --- Helper Functions ---
def get_image_base64(path):
    """Convert image to base64 string"""
    try:
        with open(path, "rb") as f:
            return base64.b64encode(f.read()).decode()
    except:
        return None

# Preload default logo
DEFAULT_LOGO_BASE64 = get_image_base64("b1.jpg") if os.path.exists("b1.jpg") else ""

# --- Initialize Gemini Chatbot with Standard Memory ---
def init_chatbot():
    if 'chatbot' not in st.session_state:
        try:
            # Get context variables
            platforms = ", ".join(st.session_state.connections.keys()) if st.session_state.connections else "None"
            business_name = st.session_state.business_info['name'] or "Not provided"
            
            # Create memory with context variables
            memory = ConversationBufferMemory(
                memory_key="history",
                return_messages=True,
                input_key="input",
                human_prefix="User",
                ai_prefix="SocialAI"
            )
            
            # Store context variables in memory
            memory.save_context(
                {"input": ""},
                {"output": f"Business: {business_name}, Platforms: {platforms}"}
            )
            
            st.session_state.memory_type = "Buffer"
            
            # Create Gemini 1.5 Flash model
            llm = ChatGoogleGenerativeAI(
                model="gemini-1.5-flash",
                google_api_key=GOOGLE_API_KEY,
                temperature=0.7,
                convert_system_message_to_human=True
            )
            
            # Custom prompt template
            template = """
            You are SocialAI, an expert social media strategist. You help users with:
            - Content creation ideas
            - Platform-specific strategies
            - Audience engagement techniques
            - Analytics interpretation
            
            Conversation History:
            {history}
            
            Current Interaction:
            User: {input}
            SocialAI:"""
            
            prompt = PromptTemplate(
                input_variables=["history", "input"],
                template=template
            )
            
            # Create conversation chain
            st.session_state.chatbot = ConversationChain(
                llm=llm,
                prompt=prompt,
                memory=memory,
                verbose=True
            )
        except Exception as e:
            st.error(f"Error initializing chatbot: {str(e)}")

# --- Simplified OAuth Flow ---
def start_oauth_flow(platform):
    """Generate authorization URL and redirect user"""
    # Generate PKCE codes
    code_verifier = base64.urlsafe_b64encode(os.urandom(40)).decode('utf-8')
    code_verifier = re.sub(r'[^a-zA-Z0-9]', '', code_verifier)
    code_challenge = hashlib.sha256(code_verifier.encode('utf-8')).digest()
    code_challenge = base64.urlsafe_b64encode(code_challenge).decode('utf-8')
    code_challenge = code_challenge.replace('=', '')
    
    # Save verifier for later
    st.session_state[f"{platform}_code_verifier"] = code_verifier
    
    # Build authorization URL
    params = {
        "response_type": "code",
        "client_id": PLATFORMS[platform]["client_id"],
        "redirect_uri": REDIRECT_URI,
        "scope": PLATFORMS[platform]["scope"],
        "state": platform,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256"
    }
    
    auth_url = PLATFORMS[platform]["authorize_url"] + "?" + "&".join(
        [f"{k}={v}" for k, v in params.items()]
    )
    
    # Redirect to authorization URL
    return auth_url

def handle_oauth_callback():
    """Handle OAuth callback from redirect"""
    query_params = st.query_params.to_dict()
    if 'code' in query_params and 'state' in query_params:
        code = query_params['code'][0] if isinstance(query_params['code'], list) else query_params['code']
        platform = query_params['state'][0] if isinstance(query_params['state'], list) else query_params['state']
        
        # Get token
        token_url = PLATFORMS[platform]["token_url"]
        data = {
            "grant_type": "authorization_code",
            "client_id": PLATFORMS[platform]["client_id"],
            "client_secret": PLATFORMS[platform]["client_secret"],
            "redirect_uri": REDIRECT_URI,
            "code": code,
            "code_verifier": st.session_state.get(f"{platform}_code_verifier", "")
        }
        
        try:
            response = requests.post(token_url, data=data)
            token_data = response.json()
            
            if 'access_token' in token_data:
                st.session_state.connections[platform] = token_data['access_token']
                
                # Get user info
                headers = {"Authorization": f"Bearer {token_data['access_token']}"}
                user_info_url = PLATFORMS[platform]["userinfo_url"]
                user_response = requests.get(user_info_url, headers=headers)
                st.session_state.user_info[platform] = user_response.json()
                
                st.success(f"Connected to {platform}!")
                
                # Clear query parameters
                st.query_params.clear()
                st.rerun()
            else:
                st.error(f"Failed to get access token: {token_data.get('error_description', '')}")
        except Exception as e:
            st.error(f"Error during authentication: {str(e)}")

# --- Sidebar: Business Info & Social Media Auth ---
def app_sidebar():
    with st.sidebar:
        # Handle OAuth callback if needed
        handle_oauth_callback()
        
        # Sidebar header with logo
        st.markdown("""
        <div style="text-align: center; margin-bottom: 20px;">
            <h2 style="color: #8B5CF6; margin-bottom: 0;">3hree.io</h2>
            <p style="opacity: 0.8; margin-top: 0;">Social Media Assistant</p>
        </div>
        """, unsafe_allow_html=True)
        
        # Business Profile Section
        st.subheader("🏢 Business Profile", divider="gray")
        with st.form("business_info_form"):
            name = st.text_input("Business Name", 
                                value=st.session_state.business_info['name'],
                                placeholder="Enter your business name")
            logo_file = st.file_uploader("Business Logo", 
                                        type=["png", "jpg", "jpeg"],
                                        help="Upload your business logo for branding")
            color = st.color_picker("Primary Brand Color", 
                                   value=st.session_state.business_info['color'])
            
            if st.form_submit_button("💾 Save Profile", use_container_width=True):
                st.session_state.business_info = {
                    'name': name,
                    'logo': logo_file,
                    'color': color
                }
                st.success("Business profile saved!")
                # Reinitialize chatbot to update context
                if 'chatbot' in st.session_state:
                    del st.session_state['chatbot']
        
        # Social Connections Section
        st.subheader("🔗 Connect Accounts", divider="gray")
        st.caption("Connect your social media platforms")
        
        # Platform Connection Buttons
        for platform in PLATFORMS:
            col1, col2 = st.columns([0.2, 0.8])
            with col1:
                # Use real platform icons if available
                icon_path = PLATFORMS[platform].get("icon_path")
                if icon_path and os.path.exists(icon_path):
                    icon_base64 = get_image_base64(icon_path)
                    st.image(f"data:image/png;base64,{icon_base64}", width=30)
                else:
                    st.write("📱")
            with col2:
                if platform in st.session_state.connections:
                    user = st.session_state.user_info.get(platform, {})
                    name = user.get('name', user.get('username', f"@{user.get('username', 'Connected')}"))
                    st.success(f"Connected as {name}")
                    if st.button(f"Disconnect {platform}", key=f"disconnect_{platform}", 
                                type="secondary", use_container_width=True):
                        st.session_state.connections.pop(platform, None)
                        st.session_state.user_info.pop(platform, None)
                        # Reinitialize chatbot to update context
                        if 'chatbot' in st.session_state:
                            del st.session_state['chatbot']
                        st.rerun()
                else:
                    if st.button(f"Connect {platform}", key=f"connect_{platform}", 
                                use_container_width=True, type="primary"):
                        auth_url = start_oauth_flow(platform)
                        st.markdown(f'<meta http-equiv="refresh" content="0; url={auth_url}">', unsafe_allow_html=True)
        
        # WhatsApp Connection
        st.subheader("💬 WhatsApp Business", divider="gray")
        st.info("Connect via Meta Business Suite")
        if st.button("Open Business Suite", key="whatsapp_help", use_container_width=True):
            js = "window.open('https://business.facebook.com')"
            st.components.v1.html(f"<script>{js}</script>", height=0)
        
        # System Status
        st.subheader("⚙️ System Status", divider="gray")
        st.caption(f"**Session ID:** `{st.session_state.session_id[:8]}...`")
        st.caption(f"**Memory:** {st.session_state.memory_type}")
        st.caption(f"**Model:** Gemini 1.5 Flash")

# --- Main Area: AI Chat Interface ---
def ai_chat_interface():
    # Initialize chatbot if not done
    if not st.session_state.get('chatbot'):
        init_chatbot()
    
    # Get business info
    business_info = st.session_state.business_info
    brand_color = business_info['color']
    
    # Get logo for AI
    if business_info['logo']:
        logo_bytes = business_info['logo'].getvalue()
        logo_base64 = base64.b64encode(logo_bytes).decode()
    else:
        logo_base64 = DEFAULT_LOGO_BASE64
    
    # Responsive CSS for both light and dark themes
    st.markdown(f"""
    <style>
        :root {{
            --primary: {brand_color};
            --secondary: #EC4899;
        }}
        
        /* Light theme variables */
        [data-theme="light"] {{
            --background: #FFFFFF;
            --card: #F8FAFC;
            --text: #0F172A;
            --border: #E2E8F0;
            --input-bg: #FFFFFF;
        }}
        
        /* Dark theme variables */
        [data-theme="dark"] {{
            --background: #0F172A;
            --card: #1E293B;
            --text: #FFFFFF;
            --border: #334155;
            --input-bg: #1E293B;
        }}
        
        .chat-container {{
            max-height: 70vh;
            overflow-y: auto;
            width: 200%;
            padding: 1px;
            border-radius: 19px;
            background: var(--card);
            margin-bottom: 20px;
            border: 1px solid var(--border);
        }}
        
        .user-message {{
            background: linear-gradient(45deg, var(--primary), var(--secondary));
            color: white;
            border-radius: 20px 20px 0 20px;
            padding: 1px;
            margin: 15px 0;
            max-width: 90%;
            float: right;
            clear: both;
        }}
        
        .ai-message {{
            background: var(--card);
            color: var(--text);
            border-radius: 18px 18px 18px 0;
            padding: 1px;
            margin: 15px 0;
            max-width: 80%;
            float: left;
            clear: both;
            border: 1px solid var(--border);
        }}
        
        .message-header {{
            display: flex;
            align-items: center;
            margin-bottom: 8px;
        }}
        
        .message-icon {{
            width: 30px;
            height: 30px;
            border-radius: 50%;
            object-fit: contain;
            margin-right: 10px;
            border: none;
            background: transparent;
        }}

        
        .message-timestamp {{
            font-size: 0.75rem;
            opacity: 0.7;
            margin-top: 8px;
            text-align: right;
        }}
        
        .stTextInput>div>div>input {{
            background: var(--input-bg) !important;
            color: var(--text) !important;
            border: 1px solid var(--border) !important;
            border-radius: 16px !important;
            padding: 10px 10px !important;
        }}
        
        .stChatInput button {{
            background: linear-gradient(45deg, var(--primary), var(--secondary)) !important;
            border-radius: 16px !important;
        }}
        
        .welcome-card {{
            background: var(--card);
            border-radius: 16px;
            padding: 2px;
            border: 1px solid var(--border);
            margin-bottom: 20px;
        }}
    </style>
    """, unsafe_allow_html=True)
    
    # Header with business info
    col1, col2 = st.columns([0.8, 0.1])
    with col1:
        st.title("3hree.io")
        st.caption("Your AI-Powered Social Media Assistant")
    
    with col2:
        if business_info['logo']:
            st.image(business_info['logo'], width=80)
        elif DEFAULT_LOGO_BASE64:
            st.image(f"data:image/png;base64,{DEFAULT_LOGO_BASE64}", width=80)
    
    # Display connected platforms
    if st.session_state.connections:
        platforms = " | ".join([f"**{p}**" for p in st.session_state.connections.keys()])
        st.info(f"🔗 Connected platforms: {platforms}")
    
    # Display business name if set
    if business_info['name']:
        st.info(f"🏢 Business: {business_info['name']}")
    
    # Welcome card
    st.markdown("""
    <div class="welcome-card">
        <h3 style="margin-top: 0;">Hello! I'm your AI-powered social media strategist</h3>
        <p>I can help you with:</p>
        <ul>
            <li>💡 Content creation ideas</li>
            <li>📊 Platform-specific strategies</li>
            <li>🤝 Audience engagement techniques</li>
            <li>📈 Analytics interpretation</li>
        </ul>
        <p>How can I assist with your social media today?</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Chat container
    chat_container = st.container()
    
    # Display chat history
    with chat_container:
        st.markdown('<div class="chat-container">', unsafe_allow_html=True)
        
        if st.session_state.chat_history:
            for msg in st.session_state.chat_history:
                if msg['role'] == 'user':
                    st.markdown(f"""
                    <div class="user-message">
                        <div class="message-header">
                            <div>👤</div>
                            <strong>You</strong>
                        </div>
                        {msg['content']}
                        <div class="message-timestamp">{msg['time']}</div>
                    </div>
                    """, unsafe_allow_html=True)
                else:
                    st.markdown(f"""
                    <div class="ai-message">
                        <div class="message-header">
                            <img src="data:image/png;base64,{logo_base64}" class="message-icon">
                            <strong>3hree.io</strong>
                        </div>
                        {msg['content']}
                        <div class="message-timestamp">{msg['time']}</div>
                    </div>
                    """, unsafe_allow_html=True)
        
        st.markdown('</div>', unsafe_allow_html=True)
    
    # Chat input with rounded corners
    user_input = st.chat_input("Ask about social media strategy...")
    
    if user_input:
        # Add user message to history
        timestamp = datetime.now().strftime("%H:%M:%S")
        st.session_state.chat_history.append({
            'role': 'user',
            'content': user_input,
            'time': timestamp
        })
        
        # Get AI response
        with st.spinner("3hree.io is thinking..."):
            try:
                response = st.session_state.chatbot.predict(input=user_input)
            except Exception as e:
                response = f"Sorry, I encountered an error: {str(e)}"
        
        # Add AI response to history
        timestamp = datetime.now().strftime("%H:%M:%S")
        st.session_state.chat_history.append({
            'role': 'ai',
            'content': response,
            'time': timestamp
        })
        
        # Rerun to update display
        st.rerun()

# --- Main App Layout ---
st.set_page_config(
    page_title="3hree.io Dashboard",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Create columns for layout
col1, col2 = st.columns([0.5, 1.5])

# Sidebar for business info and authentication
with col1:
    app_sidebar()

# Main area for chatbot
with col2:
    ai_chat_interface()
