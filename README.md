# WinRecallAnalyzer

This tool integrates Windows Recall artifacts with existing digital forensic databases to facilitate forensic analysis. It is designed to import, search, and analyze various browser histories and image capture data while offering data recovery features to restore lost records.

## Requirements

- Python 3.12.7 64-bit
- Required libraries:
  - PySide6: Qt-based GUI framework (v6.6.1)
  - pandas: Data manipulation and analysis (v2.2.0)
  - sqlparse: SQL parsing and formatting (v0.4.4)

You can install all required packages using:

```
pip install -r requirements.txt
```

## What is Windows Recall?

<p align="center">
  <img src="https://github.com/user-attachments/assets/0a8243b3-955f-4267-9e8a-de231e305677" alt="recall_logo">
</p>
1. Windows Recall captures a screen snapshot every 5 seconds and applies OCR, storing the results in a searchable database.</br>
2. This enables users to easily revisit and find past screen content directly from the database.</br>

## TO DO LIST

- [x] Implement All Table
- [x] Implement Image Table
- [ ] Implement File Table
- [ ] Implement Web Table
- [ ] Implement App Table
- [ ] Add SRUM Analysis
- [ ] Add Initial Recovery Results
- [ ] Convert .py to .exe binary file

## License

Code and documentation copyright 2024 the WinRecallAnalyzer Authors. Code released under the [MIT LICENSE](https://github.com/Perk31e/WinRecallAnalyzer/blob/main/LICENSE).

## Contributing

Contributions are what make the open-source community such an amazing place to learn, inspire, and create. Any contributions you make are **greatly appreciated**. For detailed guidelines, please refer to our [CONTRIBUTING](https://github.com/Perk31e/WinRecallAnalyzer/blob/main/CONTRIBUTING.md).
