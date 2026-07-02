# PLC Universal Simulator - Architecture

## Version

Target architecture: v2.0

---

## Goal

PLC Universal Simulator is a universal engineering tool for simulating, monitoring and testing PLC signals across different automation platforms.

The main goal of version 2.0 is to make the **Tag Manager** the single source of truth for the whole application.

---

## Core Principle

All application modules must consume the same tag database.

```text
Tag Manager
     |
     +--> Digital Inputs
     +--> Analog Inputs
     +--> Feedbacks
     +--> Trends
     +--> Alarms
     +--> Dashboard
     +--> PID