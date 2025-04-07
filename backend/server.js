import express from "express";
import axios from "axios";
import cors from "cors";
import dotenv from "dotenv";

dotenv.config();

const app = express();
app.use(cors()); // Allow frontend to communicate with backend
app.use(express.json()); // Parse JSON requests

const CLIENT_ID = process.env.LINKEDIN_CLIENT_ID;
const CLIENT_SECRET = process.env.LINKEDIN_CLIENT_SECRET;
const REDIRECT_URI = "http://localhost:5173/callback"; // Must match LinkedIn settings
const ACCOUNT_SERVICE_URL = "http://localhost:5001"; // URL of the account service

// 🚀 Exchange Authorization Code for Access Token
app.post("/auth/linkedin/callback", async (req, res) => {
    const { code } = req.body;
    console.log("Received LinkedIn callback with code:", code);
    
    try {
        // Exchange the authorization code for an access token
        const tokenResponse = await axios.post("https://www.linkedin.com/oauth/v2/accessToken", new URLSearchParams({
            grant_type: "authorization_code",
            code,
            redirect_uri: REDIRECT_URI,
            client_id: CLIENT_ID,
            client_secret: CLIENT_SECRET,
        }));

        const accessToken = tokenResponse.data.access_token;

        // Fetch user profile using OpenID Connect
        const userInfo = await axios.get("https://api.linkedin.com/v2/userinfo", {
            headers: { Authorization: `Bearer ${accessToken}` },
        });

        // Process the user info and create/link account
        const accountResponse = await axios.post(`${ACCOUNT_SERVICE_URL}/auth/linkedin`, {
            email: userInfo.data.email,
            name: userInfo.data.name,
            picture: userInfo.data.picture
        });

        // Return the account data to the frontend
        res.json(accountResponse.data);

    } catch (error) {
        console.error("Error in LinkedIn authentication:", error.response?.data || error);
        res.status(500).json({ 
            code: 500,
            message: "Authentication failed",
            error: error.response?.data || error.message
        });
    }
});

// Start Server
app.listen(3000, () => console.log("🚀 Server running on http://localhost:3000"));
