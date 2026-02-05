# Playwright Testing Files - LOCAL ONLY

## ⚠️ IMPORTANT: These files are for LOCAL TESTING ONLY
**DO NOT commit these files to git** - they are excluded in `.gitignore`

## Purpose
These files were created for local browser testing and debugging of the Streamlit UI. They use Playwright to automate browser interactions and take screenshots.

---

## Files Overview

### 1. **browser_monitor.py** - Main Testing Tool
**Status**: 🔧 Local testing tool  
**Purpose**: Interactive browser monitoring for Streamlit app
**Features**:
- Launch browser and navigate to localhost:5555
- Take screenshots
- Monitor console logs
- Check button visibility and positioning
- Interactive mode and auto-monitoring mode

**Usage**:
```bash
# Interactive mode
python3 browser_monitor.py

# Auto-monitoring mode (takes screenshots every 10 seconds)
python3 browser_monitor.py auto
```

**Keep?**: No - this is a temporary testing tool

---

### 2. **layout_monitor.py** - Layout Testing
**Status**: 🔧 Local testing tool  
**Purpose**: Monitor and verify Streamlit layout issues
**Features**:
- Check if control buttons are visible
- Verify fixed positioning
- Compare before/after layout changes

**Usage**:
```bash
python3 layout_monitor.py
```

**Keep?**: No - specific to a layout bug investigation

---

### 3. **login_monitor.py** - Login Flow Testing
**Status**: 🔧 Local testing tool  
**Purpose**: Test Spotify OAuth login flow
**Features**:
- Automate login sequence
- Capture screenshots at each step
- Verify authentication works

**Usage**:
```bash
python3 login_monitor.py
```

**Keep?**: No - one-time testing tool

---

### 4. **quick_screenshot.py** - Quick Screenshot Tool
**Status**: 🔧 Local utility  
**Purpose**: Quickly capture a screenshot of the running app

**Usage**:
```bash
python3 quick_screenshot.py
```

**Keep?**: No - convenience tool for debugging

---

### 5. **screenshot_summary.py** - Screenshot Analysis
**Status**: 🔧 Local utility  
**Purpose**: Analyze and summarize screenshots taken during testing

**Usage**:
```bash
python3 screenshot_summary.py
```

**Keep?**: No - post-testing analysis tool

---

### 6. **test_login_ui.py** - Login UI Test
**Status**: 🔧 Local test  
**Purpose**: Automated test for login UI

**Keep?**: No - specific test case

---

## Generated Files (Also Excluded)

### Screenshots
- `screenshots/` directory - All screenshots from testing
- `layout_*.png` - Layout investigation screenshots
- `state_*.png` - UI state screenshots
- `streamlit_*.png` - General Streamlit screenshots

### Analysis Files
- `layout_analysis.json` - Layout analysis results

---

## Why These Are Excluded

1. **Environment-Specific**: These tools test against `localhost:5555`
2. **Temporary**: Created for specific debugging sessions
3. **Not Production Code**: Not part of the application's core functionality
4. **Heavy Dependencies**: Require Playwright which is not needed for production
5. **Personal Testing**: Screenshots may contain personal Spotify data

---

## Cleanup

If you want to remove all Playwright testing files:

```bash
# Remove testing scripts
rm browser_monitor.py layout_monitor.py login_monitor.py
rm quick_screenshot.py screenshot_summary.py test_login_ui.py

# Remove generated files
rm -f *.png layout_analysis.json
rm -rf screenshots/

# Remove Playwright dependencies (optional)
pip uninstall playwright
```

---

## What TO Commit

### Core Application Files ✅
- `app.py` - Main Streamlit app
- `ai_manager.py` - AI function calling
- `mcp_manager.py` - MCP integration
- `spotify_manager.py` - Spotify API wrapper
- `spotify_mcp_server.py` - MCP server
- `conversation_manager.py` - Conversation persistence
- `configuration_manager.py` - Configuration handling

### Documentation ✅
- `README.md` - Project documentation
- `docs/*.md` - All documentation files
- `conf.py.template` - Configuration template (without secrets)

### Configuration ✅
- `.gitignore` - Git exclusions
- `requirements.txt` - Python dependencies
- `pyproject.toml` - Project metadata
- `Dockerfile` - Docker configuration

### Tools ✅
- `tools/test_mcp_server.py` - MCP server tests
- `tools/test_mcp_ai_integration.py` - MCP AI integration tests
- `tools/test_combine_playlists.py` - Combine playlists test

### AWS Deployment ✅
- `aws/*.json` - AWS policy documents
- `aws/README.md` - Deployment docs
- `aws/nginx-jemya.conf` - Nginx config

---

## Summary

**Playwright Testing Files**: 🚫 **DO NOT COMMIT** - Local testing only  
**Core Application**: ✅ **COMMIT** - Part of the project  
**Documentation**: ✅ **COMMIT** - Helps other developers  
**Generated Files**: 🚫 **DO NOT COMMIT** - Personal/temporary data

The `.gitignore` has been updated to automatically exclude all Playwright-related files.
