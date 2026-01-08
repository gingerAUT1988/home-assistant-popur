# Popur Litter Box Integration for Home Assistant

<p align="center">
  <img src="images/icon.png" width="150" height="150" alt="Popur Logo">
</p>

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)
...
[![version](https://img.shields.io/github/v/release/gingerAUT1988/home-assistant-popur)](https://github.com/gingerAUT1988/home-assistant-popur)
[![Home Assistant](https://img.shields.io/badge/Home%20Assistant-2024.1-blue.svg)](https://www.home-assistant.io/)

A custom component to integrate the **Popur X5 Self-Cleaning Litter Box** into Home Assistant. 

Since Popur does not provide a local API, this integration communicates with the Popur Cloud via MQTT and HTTP to fetch status updates and send commands.

## 🐱 Features

*   **Multi-Device Support:** Automatically discovers all Popur X5 devices on your account.
*   **Real-time Controls:**
    *   Trigger "Clean" cycle.
    *   Toggle "Manual Mode" (used for Do Not Disturb/Night Mode).
*   **Sensors:**
    *   **Bin Full:** Binary sensor indicating when the waste bin needs emptying.
    *   **Cycles:** Tracks the number of daily cleaning cycles (Recommendation: Use Home Assistant 'Utility Meter' Helpers to track daily usage locally, as the device's internal counters may reset based on China Standard Time.) 
*   **Easy Setup:** Fully configurable via the Home Assistant UI (Config Flow). No YAML editing required for connection.

## 📥 Installation

### Option 1: Via HACS (Recommended)

1.  Open **HACS** in Home Assistant.
2.  Go to **Integrations** > click the **3 dots** (top right) > **Custom repositories**.
3.  Paste the URL of this repository: `https://github.com/gingerAUT1988/home-assistant-popur-x5`
4.  Select Category: **Integration**.
5.  Click **Add**, then click **Download**.
6.  **Restart Home Assistant**.

### Option 2: Manual Installation

1.  Download the `popur` folder from this repository.
2.  Copy the `popur` folder into your Home Assistant's `custom_components` directory.
    *   Path: `/config/custom_components/popur/`
3.  **Restart Home Assistant**.

## ⚙️ Configuration

1.  Go to **Settings** > **Devices & Services**.
2.  Click **+ Add Integration**.
3.  Search for **Popur X5**.
4.  Enter your Popur App **Email** and **Password**.
5.  The integration will automatically find your devices and add them to Home Assistant.

---

## 🌙 Night Mode (Do Not Disturb) Automation

To prevent the robot from cycling at night, you can use the "Manual Mode" switch. We recommend using a **Schedule Helper** combined with an automation.

### 1. Create a Schedule
Go to **Settings** > **Devices & Services** > **Helpers** > **Create Helper** > **Schedule**.
*   **Name:** `Popur Quiet Hours`
*   **Entity ID:** `schedule.popur_quiet_hours`
*   *Draw the blocks on the calendar where you want the toilet to be SILENT (e.g., 22:00 to 07:00).*

### 2. Create the Automation
We have provided a Blueprint (coming soon) or you can use this automation logic. This ensures the toilet enters Manual Mode at night and **automatically performs a safety clean** when it wakes up in the morning.

```yaml
alias: "Popur: Night Mode Manager"
mode: restart
trigger:
  - platform: state
    entity_id: schedule.popur_quiet_hours
    from: "off"
    to: "on"
    id: "sleep"
  - platform: state
    entity_id: schedule.popur_quiet_hours
    from: "on"
    to: "off"
    id: "wake"
action:
  - choose:
      # Enter Night Mode
      - conditions:
          - condition: trigger
            id: "sleep"
        sequence:
          - service: switch.turn_on
            target:
              entity_id: 
                - switch.popur_klo_manual_mode
                # - switch.popur_bad_manual_mode (Add second device if needed)

      # Wake Up & Clean
      - conditions:
          - condition: trigger
            id: "wake"
        sequence:
          - service: switch.turn_off
            target:
              entity_id: 
                - switch.popur_klo_manual_mode
          # Wait 10s for mode switch, then clean
          - delay: 10
          - service: button.press
            target:
              entity_id: 
                - button.popur_klo_clean
```
## 📊 Compact Dashboard Card
Here is a clean, compact Lovelace card configuration using standard Tile cards and a History Graph. This assumes you have created a schedule.popur_quiet_hours helper.

```yaml
type: vertical-stack
cards:
  - type: conditional
    conditions:
      - entity: binary_sensor.bin_full_2
        state: "on"
    card:
      type: tile
      entity: binary_sensor.bin_full_2
      name: Klo is FULL!
      color: red
      icon: mdi:delete-alert
  - type: conditional
    conditions:
      - entity: binary_sensor.bin_full
        state: "on"
    card:
      type: tile
      entity: binary_sensor.bin_full
      name: Bad is FULL!
      color: red
      icon: mdi:delete-alert
  - type: history-graph
    title: Usage
    hours_to_show: 24
    refresh_interval: 60
    entities:
      - entity: sensor.cycles_2
        name: Klo
      - entity: sensor.cycles
        name: Bad
  - type: tile
    entity: schedule.popur_quiet_hours
    name: Quiet Hours (Tap to Edit)
    icon: mdi:clock-time-eight-outline
    color: indigo
  - type: grid
    columns: 2
    square: false
    cards:
      - type: vertical-stack
        cards:
          - type: heading
            heading: Klo
            icon: mdi:cat
          - type: tile
            entity: button.clean_2
            name: Clean Now
            icon: mdi:robot-vacuum
            color: teal
            vertical: false
            tap_action:
              action: press
          - type: grid
            columns: 2
            square: false
            cards:
              - type: tile
                entity: sensor.klo_daily
                name: Today
                icon: mdi:counter
                color: light-blue
                vertical: true
              - type: tile
                entity: input_boolean.popur_klo_dnd_enabled
                name: Auto Night
                icon: mdi:weather-night
                color: deep-purple
                vertical: true
              - type: tile
                entity: switch.manual_mode_2
                name: DND Mode
                icon: mdi:volume-off
                color: orange
                vertical: true
              - type: tile
                entity: sensor.cycles_2
                name: Bin Cycles
                icon: mdi:delete-variant
                color: grey
                vertical: true
      - type: vertical-stack
        cards:
          - type: heading
            heading: Bad
            icon: mdi:cat
          - type: tile
            entity: button.clean
            name: Clean Now
            icon: mdi:robot-vacuum
            color: teal
            vertical: false
            tap_action:
              action: press
          - type: grid
            columns: 2
            square: false
            cards:
              - type: tile
                entity: sensor.bad_daily
                name: Today
                icon: mdi:counter
                color: light-blue
                vertical: true
              - type: tile
                entity: input_boolean.popur_bad_dnd_enabled
                name: Auto Night
                icon: mdi:weather-night
                color: deep-purple
                vertical: true
              - type: tile
                entity: switch.manual_mode
                name: DND Mode
                icon: mdi:volume-off
                color: orange
                vertical: true
              - type: tile
                entity: sensor.cycles
                name: Bin Cycles
                icon: mdi:delete-variant
                color: grey
                vertical: true
```
## ☕ Support
This integration was reverse-engineered. If it helps you keep your cats happy and your house clean, feel free to say thanks!
## ⚠️ Disclaimer
This is a custom integration and is not affiliated with Popur. Use at your own risk. The API limits or methods may change at any time.
