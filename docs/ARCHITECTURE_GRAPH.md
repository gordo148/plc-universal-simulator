# PLC Universal Simulator — Architecture and Dependency Graphs

## Purpose

This document visualizes the current architecture, runtime flows, dependency cycle, persistence, build path, and recommended target boundaries. Paths in nodes refer to repository modules.

## Current high-level architecture

```mermaid
flowchart TB
    Main["main.py<br/>bootstrap and logging"] --> App["ui/main_window.py<br/>PLCSimulator"]
    App --> UI["ui/*<br/>feature views and callbacks"]
    App --> PLC["services/plc_service.py<br/>PLCService"]
    App --> Runtime["core/tag_runtime.py<br/>RuntimeTagCache"]
    App --> Settings["services/settings_service.py"]
    UI --> Tags["core/tag_model.py<br/>TagDefinition"]
    UI --> Runtime
    UI --> Project["ui/project_config.py"]
    UI --> CSV["ui/tag_manager.py<br/>CSV import/export"]
    PLC --> Runtime
    PLC --> Drivers["drivers/*"]
    Project --> Tags
    CSV --> Tags
```

## Current feature data flow

```mermaid
flowchart LR
    Files[".simproject / CSV"] --> Definitions["app.tags<br/>TagDefinition list"]
    Definitions --> Service["PLCService"]
    Definitions --> Digital["Digital"]
    Definitions --> Analog["Analog"]
    Definitions --> Feedback["Feedbacks"]
    Definitions --> Alarms["Alarms"]
    Definitions --> Trends["Trends"]
    Definitions --> Dashboard["Dashboard"]
    Service --> Cache["RuntimeTagCache"]
    Simulator["Simulation/PID"] --> Cache
    Cache --> Digital
    Cache --> Analog
    Cache --> Feedback
    Cache --> Alarms
    Cache --> Trends
    Cache --> Dashboard
```

## Current PLC connection and polling flow

```mermaid
sequenceDiagram
    participant UI as Tk / PLCSimulator
    participant Worker as Connection thread
    participant Queue as queue.Queue
    participant PLC as PLCService
    participant Driver as Driver
    participant Cache as RuntimeTagCache

    UI->>Worker: connect brand/settings
    Worker->>PLC: connect()
    PLC->>Driver: connect()
    Worker->>Queue: result/error
    UI->>Queue: poll every 25 ms
    Note over UI,Driver: Connection is asynchronous
    loop every 500 ms
        UI->>PLC: read(tags)
        PLC->>Driver: synchronous network read
        Driver-->>PLC: values/errors
        PLC->>Cache: sync/update/invalidate
        PLC-->>UI: result
        UI->>UI: update widgets/Feedback/Dashboard
    end
    Note over UI,Driver: Cyclic reads currently execute on Tk thread
```

## Internal module dependency cycle

```mermaid
flowchart LR
    Alarm["ui/alarm_tab.py"] --> Dashboard["ui/dashboard_tab.py"]
    Alarm --> Tags["ui/tag_manager.py"]
    Dashboard --> Digital["ui/digital_tab.py"]
    Dashboard --> Analog["ui/analog_tab.py"]
    Dashboard --> Tags
    Digital --> Project["ui/project_config.py"]
    Digital --> Tags
    Analog --> Project
    Analog --> Tags
    Project --> Alarm
    Project --> Dashboard
    Project --> Digital
    Project --> Analog
    Project --> Tags
    Tags --> Analog
```

The six nodes above form one strongly connected component. Some edges use local imports, which defer rather than eliminate the cycle.

## PLC driver routing

```mermaid
flowchart TB
    Service["services/plc_service.py"] --> Registry["_DRIVER_IMPORTS<br/>lazy concrete imports"]
    Registry --> Siemens["drivers/siemens_s7.py"]
    Registry --> Schneider["drivers/schneider_modbus.py"]
    Registry --> Modbus["drivers/modbus_tcp.py"]
    Registry --> Rockwell["drivers/rockwell_enip.py"]
    Registry --> Omron["drivers/omron_fins.py"]
    Registry --> Internal["drivers/internal_simulator.py"]
    Service --> S7Address["drivers/siemens_address.py"]
    Service --> Codecs["brand-specific parsing,<br/>batching and decoding"]
```

## Persistence flow

```mermaid
flowchart TB
    Open["Open project"] --> Parse["json.load"]
    Parse --> Migrate["migrate_project_data"]
    Migrate --> Validate["_validate_project_data"]
    Validate --> Stage["_stage_project_data / deep copy"]
    Stage --> Apply["_apply_project_data"]
    Apply --> UIState["Widgets and app state"]
    Apply --> Runtime["RuntimeTagCache sync"]
    Apply -. failure .-> Rollback["Restore project/runtime snapshot"]
    Save["build_project_data"] --> Temp["temporary file + flush + fsync"]
    Temp --> Replace["os.replace"]
```

## Current callback topology

```mermaid
flowchart TB
    Scheduler["PLCSimulator.schedule_job"] --> PLC["PLC read<br/>500 ms"]
    Scheduler --> Feedback["Feedback scan<br/>500 ms"]
    Scheduler --> Alarm["Alarm scan<br/>500 ms"]
    Scheduler --> Dashboard["Dashboard refresh<br/>750 ms"]
    Scheduler --> Trend["Trend sample/redraw<br/>1000 ms"]
    Scheduler --> PID["PID loop<br/>configurable"]
    Scheduler --> Analog["Analog simulation<br/>configurable"]
    PLC --> Feedback2["additional Feedback update"]
    PLC --> Dashboard2["additional Dashboard update"]
```

## Build and version flow

```mermaid
flowchart LR
    Git["Git tags/commit/status"] --> Generator["scripts/generate_version.py"]
    Generator --> Metadata["core/generated/build_metadata.py<br/>Git ignored"]
    Metadata --> Adapter["core/version.py<br/>static public adapter"]
    Adapter --> Source["Source runtime"]
    Metadata --> Spec["plc-universal-simulator.spec"]
    Spec --> Linux["Linux one-folder bundle"]
    Spec --> Windows["Windows executable"]
```

## Recommended near-term runtime architecture

```mermaid
flowchart TB
    Tk["Tk presentation"] --> Commands["Application commands"]
    Commands --> RuntimeController["RuntimeController"]
    RuntimeController --> Poller["Polling worker"]
    Poller --> Session["PLCSession / driver adapter"]
    Session --> Driver["Protocol driver"]
    Poller --> Changes["Immutable RuntimeChangeSet"]
    Changes --> Queue["Bounded queue"]
    Queue --> Dispatcher["Tk-thread event dispatcher"]
    Dispatcher --> Dashboard["Dashboard view model"]
    Dispatcher --> Feedback["Feedback Engine + view"]
    Dispatcher --> Alarms["Alarm Engine + view"]
    Dispatcher --> Trends["Trend history service + view"]
    Dispatcher --> Simulation["Digital/Analog selected views"]
```

## Recommended target architecture

```mermaid
flowchart TB
    subgraph Presentation
        Desktop["Tk Desktop"]
        Web["Future Web"]
        REST["Future REST/WebSocket"]
        CLI["Future CLI"]
    end
    subgraph Application
        Cmd["Commands / Queries"]
        Bus["Typed Event Bus"]
        RuntimeEngine["Runtime Engine"]
        FeedbackEngine["Feedback Engine"]
        AlarmEngine["Alarm Engine"]
        ProjectService["Project Service"]
        ScenarioService["Recipe / Scenario Services"]
    end
    subgraph Domain
        Tag["Tag / Stable ID"]
        RuntimeValue["Runtime Value / Quality"]
        FeedbackModel["Feedback state machine"]
        AlarmModel["Alarm state machine"]
        RecipeModel["Recipe / Scenario models"]
    end
    subgraph Infrastructure
        DriverRegistry["Driver Registry / Sessions"]
        Stores["Project / Settings / History"]
        CSV["CSV adapters"]
        OPC["Future OPC UA"]
        MQTT["Future MQTT"]
        Plugins["Future Plugin Host"]
    end

    Desktop --> Cmd
    Web --> Cmd
    REST --> Cmd
    CLI --> Cmd
    Cmd --> RuntimeEngine
    Cmd --> FeedbackEngine
    Cmd --> AlarmEngine
    Cmd --> ProjectService
    Cmd --> ScenarioService
    RuntimeEngine --> Bus
    FeedbackEngine --> Bus
    AlarmEngine --> Bus
    Application --> Domain
    Application --> Infrastructure
```

## Boundary rules for future work

1. Domain modules must not import Tk or protocol libraries.
2. Presentation must not access concrete drivers.
3. Driver adapters must publish typed results rather than mutate widgets.
4. Project/CSV parsing must be callable without constructing `PLCSimulator`.
5. Workers must never update Tk widgets.
6. Feature engines must use stable tag IDs and explicit quality.
7. Plugins must depend on published application ports, not dynamic `app` attributes.
