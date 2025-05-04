import React, { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';

function LoginPage() {
  const navigate = useNavigate();

  useEffect(() => {
    // Check if the user is logged in before redirecting
    fetch("/me")
      .then((res) => {
        if (res.ok) {
          // User is already logged in, redirect to the home page
          navigate('/');
        } else {
          // Not logged in, continue with the Spotify login flow
          window.location.href = "/login";
        }
      })
      .catch(() => {
        // If the check fails, assume user is not logged in and continue the login process
        window.location.href = "/login";
      });
  }, [navigate]);

  return (
    <div className="login-page">
      <h2>Redirecting to Spotify...</h2>
      <p>Please wait while we redirect you to Spotify for authentication.</p>
      <p>If the page doesn't redirect in a few seconds, <a href="/login">click here</a>.</p>
    </div>
  );
}

export default LoginPage;
