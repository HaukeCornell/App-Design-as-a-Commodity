# Vibe Coding Art Installation - TODO List

## Overview
This document tracks the development tasks for transforming the Vibe Coder prototype into a complete art installation. The installation allows users to request custom apps by sending money via Venmo, with the app's quality/features determined by the payment amount ("vibe coding").

## Tasks

### Documentation & Planning
- [x] Create comprehensive README explaining the art installation concept
- [ ] Document API keys and environment variables needed
- [ ] Remove unnecessary code (timer example, ethic tiers (dark, bright))

### GitHub Integration Enhancement
- [ ] Implement automatic GitHub repository creation (instead of manual)
  - [ ] Research GitHub API for repository creation
  - [ ] Implement authentication with GitHub API using PAT
  - [ ] Create function to automatically create new repositories
  - [ ] Update existing GitHub push functionality to use new repo creation
  - [ ] Add error handling for API rate limits and failures

### Venmo Email Monitoring
- [ ] Set up email monitoring system for Venmo payment confirmations
  - [ ] Research IMAP/POP3 libraries for Python
  - [ ] Create email authentication system (secure storage for credentials)
  - [ ] Implement email polling mechanism (interval-based)
  - [ ] Develop parser for Venmo confirmation emails
    - [ ] Extract sender information
    - [ ] Extract payment amount
    - [ ] Extract payment note (app request)
  - [ ] Create queue system for processing multiple incoming requests
  - [ ] Add logging for email monitoring activities

### Multi-Iteration Vibe Coding Enhancement
- [ ] Implement tiered app generation based on payment amount
  - [ ] Define clear payment tiers and corresponding features
  - [ ] Research integration with aider.chat
  - [ ] Implement multi-pass generation system
    - [ ] Initial app generation
    - [ ] Quality/feature enhancement based on payment tier
    - [ ] Code refinement and testing
  - [ ] Create feedback loop for iterative improvements
  - [ ] Implement timeout/fallback mechanisms for reliability

### Receipt Printer Integration
- [ ] Set up Epson receipt printer functionality
  - [ ] Research ESC/POS command set for the printer
  - [ ] Install necessary printer drivers on development system
  - [ ] Create Python wrapper for ESC/POS commands
  - [ ] Design receipt layout
    - [ ] App name and description
    - [ ] QR code for accessing the app
    - [ ] GitHub repository URL
    - [ ] Payment amount and tier information
  - [ ] Implement print queue system
  - [ ] Add error handling for printer issues

### Raspberry Pi Deployment
- [ ] Prepare Raspberry Pi for installation
  - [ ] Install required OS and dependencies
  - [ ] Configure network settings for public access
  - [ ] Set up environment variables for API keys
  - [ ] Configure startup script for automatic launch
  - [ ] Implement monitoring and auto-restart functionality
  - [ ] Test all components on Raspberry Pi hardware
  - [ ] Create backup/restore procedure

### Final Integration & Testing
- [ ] Integrate all components into cohesive system
  - [ ] Create main control loop connecting all modules
  - [ ] Implement comprehensive logging system
  - [ ] Create admin interface for monitoring and management
  - [ ] Conduct end-to-end testing of complete workflow
  - [ ] Develop troubleshooting guide for common issues

## Progress Tracking
- [ ] Initial prototype enhancement (Current: Basic prototype with simulated payment)
- [ ] Alpha version (Email monitoring + GitHub automation)
- [ ] Beta version (Multi-iteration + Printer integration)
- [ ] Release candidate (Full system on development hardware)
- [ ] Final installation (Deployed on Raspberry Pi in exhibition space)
