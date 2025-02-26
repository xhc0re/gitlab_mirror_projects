# GitLab Mirror Tool - Pełna instrukcja instalacji i konfiguracji

## 1. Przegląd

GitLab Mirror Tool to narzędzie umożliwiające efektywne kopiowanie (mirroring) projektów między instancjami GitLab. Narzędzie obsługuje:
- Mirrowanie projektów z zachowaniem oryginalnej struktury grup
- Mirrowanie projektów do nowej struktury grup
- Weryfikację statusu mirrorów
- Wyzwalanie synchronizacji mirrorów
- Aktualizację istniejących mirrorów

## 2. Wymagania systemowe

- Python 3.7 lub nowszy
- Git
- Dwie instancje GitLab (źródłowa i docelowa)
- Tokeny dostępu do obu instancji GitLab

## 3. Pobieranie i instalacja

### 3.1. Klonowanie repozytorium

```bash
git clone <URL_REPOZYTORIUM> gitlab-mirror
cd gitlab-mirror
```

### 3.2. Tworzenie wirtualnego środowiska

```bash
python -m venv .venv
```

### 3.3. Aktywacja wirtualnego środowiska

Na systemach Linux/macOS:
```bash
source .venv/bin/activate
```

Na Windows (CMD):
```bash
.venv\Scripts\activate
```

Na Windows (PowerShell):
```bash
.venv\Scripts\Activate.ps1
```

### 3.4. Instalacja zależności

```bash
pip install -r requirements.txt
```

### 3.5. Instalacja pakietu w trybie deweloperskim

```bash
pip install -e .
```

## 4. Konfiguracja

### 4.1. Automatyczna konfiguracja

Możesz użyć skryptu konfiguracyjnego:

```bash
python setup_env.py
```

Skrypt przeprowadzi Cię przez proces konfiguracji i utworzy wszystkie potrzebne pliki.

### 4.2. Ręczna konfiguracja

1. Utwórz plik `.env` w głównym katalogu projektu:

```
SOURCE_GITLAB_URL="https://gitlab.source.com"
SOURCE_GITLAB_TOKEN="twój_token_źródłowy"
TARGET_GITLAB_URL="https://gitlab.target.com"
TARGET_GITLAB_TOKEN="twój_token_docelowy"
PROJECTS_FILE="projects.csv"
ASSIGN_USERS_TO_GROUPS=true
```

2. Utwórz plik `projects.csv` zawierający mapowanie projektów:

```csv
group1/project1,newgroup1
group2/subgroup1/project2,
group3/project3,othergroup
```

Gdzie:
- Pierwsza kolumna to ścieżka projektu w źródłowym GitLabie
- Druga kolumna to grupa docelowa w docelowym GitLabie:
  - Jeśli podana, projekt będzie przeniesiony do tej grupy
  - Jeśli pusta, projekt zachowa oryginalną strukturę grup

## 5. Użycie

### 5.1. Mirrowanie projektów

```bash
gitlab-mirror
```

lub z parametrami:

```bash
gitlab-mirror --source-url=https://gitlab.source.com --source-token=token --target-url=https://gitlab.target.com --target-token=token --projects-file=projects.csv
```

### 5.2. Weryfikacja statusu mirrorowania

```bash
gitlab-mirror-verify --projects-file=projects.csv
```

Ta komenda sprawdza, czy wszystkie projekty zostały poprawnie zmirrowane i generuje raporty:
- `01-missing-in-target.csv` - projekty, które nie istnieją w instancji docelowej
- `02-missing-mirrors.csv` - projekty bez skonfigurowanych mirrorów
- `03-failed-mirrors.csv` - projekty z niedziałającymi mirrorami
- `00-fix.csv` - lista wszystkich projektów wymagających naprawy

### 5.3. Wyzwalanie synchronizacji mirrorów

```bash
gitlab-mirror-trigger --projects-file=projects.csv
```

Ta komenda wymusza synchronizację istniejących mirrorów projektów z pliku CSV.

### 5.4. Aktualizacja istniejących mirrorów

```bash
gitlab-mirror-update --pattern="stara-domena" --update-failed
```

Ta komenda aktualizuje istniejące mirrory, które:
- Zawierają określony wzorzec w URL (np. starą domenę)
- Są oznaczone jako niedziałające (z błędami autentykacji)

### 5.5. Kompatybilność wsteczna

Dla kompatybilności z poprzednią wersją, nadal można używać:

```bash
python main.py
```

## 6. Struktura projektu

```
gitlab-mirror/
├── setup.py                           # Konfiguracja setuptools
├── requirements.txt                   # Zależności projektu
├── main.py                            # Skrypt główny dla kompatybilności
├── .env                               # Konfiguracja zmiennych środowiskowych
├── .env.example                       # Przykładowa konfiguracja
├── setup_env.py                       # Skrypt konfiguracyjny
├── projects.csv                       # Plik z mapowaniem projektów
├── gitlab_mirror/                     # Pakiet główny
│   ├── __init__.py
│   ├── core/                          # Moduły core
│   │   ├── __init__.py
│   │   ├── config.py                  # Konfiguracja
│   │   ├── mirror.py                  # Logika mirrora 
│   │   ├── decryptor.py               # Dekryptor
│   │   ├── exceptions.py              # Definicje wyjątków
│   │   └── user_migration.py          # Migracja użytkowników
│   ├── utils/                         # Narzędzia pomocnicze
│   │   ├── __init__.py
│   │   ├── verify.py                  # Weryfikacja
│   │   ├── trigger.py                 # Wyzwalanie mirrorów
│   │   └── update.py                  # Aktualizacja mirrorów
│   └── cli/                           # Interfejs CLI
│       ├── __init__.py
│       ├── main.py                    # Główny punkt wejścia CLI
│       └── commands/                  # Komendy CLI
│           ├── __init__.py
│           ├── mirror_command.py      # Komenda mirrora
│           ├── verify_command.py      # Komenda weryfikacji
│           └── update_command.py      # Komenda aktualizacji
└── tests/                             # Testy
    ├── __init__.py
    └── test_imports.py                # Testy importów
```

## 7. Rozwiązywanie problemów

### Brak połączenia z GitLabem
- Sprawdź, czy URL GitLaba jest poprawny
- Upewnij się, że token ma wystarczające uprawnienia (minimum: API, read_repository, write_repository)

### Problemy z mirrorowaniem
- Użyj komendy `gitlab-mirror-verify` dla diagnozy problemów
- Sprawdź w logach GitLaba źródłowego błędy związane z push mirror

### Problemy z importami
- Uruchom `python -m tests.test_imports`, aby sprawdzić poprawność importów
- Upewnij się, że wszystkie zależności są zainstalowane: `pip install -r requirements.txt`

## 8. Wsparcie i rozwój

Zgłaszaj problemy i sugestie poprzez system issues GitLaba.