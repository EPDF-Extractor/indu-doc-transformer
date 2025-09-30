# God Factory Tests

This directory contains comprehensive tests for the `God` factory class and related functionality.

## Test Files

### test_creation.py (47 tests)
Tests for object creation methods:
- **TestGodInitialization**: God class initialization and representation
- **TestCreateAttribute**: Attribute creation with different types and validation
- **TestCreateTag**: Tag creation, caching, and edge cases
- **TestCreateXTarget**: XTarget creation with various configurations
- **TestCreatePin**: Pin and pin chain creation
- **TestCreateLink**: Link creation and merging
- **TestCreateConnection**: Connection creation with/without cables and links
- **TestGodIntegration**: Full workflow integration tests
- **TestGodEdgeCases**: Edge cases like self-connections and duplicate attributes

### test_no_duplicates.py (25 tests)
Tests for object caching and duplicate prevention:
- **TestNoDuplicateXTargets**: XTarget deduplication and attribute merging
- **TestNoDuplicateConnections**: Connection caching and uniqueness
- **TestNoDuplicateTags**: Tag caching
- **TestNoDuplicatePins**: Pin caching
- **TestNoDuplicateLinks**: Link caching and merging
- **TestNoDuplicateAttributes**: Attribute caching
- **TestComplexNoDuplicatesScenarios**: Complex workflows with multiple object types

### test_god_coverage.py (23 tests) 
**NEW** - Tests for improved code coverage:
- **TestPagesObjectsMapper**: Page-object mapping functionality
  - Mapper initialization
  - Edge cases: null page numbers, null parents
  - Getting objects on a page
  - Getting pages of an object (by object or string GUID)
  - Nonexistent page/object handling

- **TestTagCreationFailure**: Tag creation error paths
  - Tag creation returning None

- **TestXTargetCreationFailure**: XTarget creation error paths
  - XTarget creation failing when tag creation fails

- **TestPinCreationFailure**: Pin creation edge cases
  - Empty pin names
  - Impossible null cases

- **TestMultiplePageMappings**: Objects appearing on multiple pages
  - XTargets on multiple pages
  - Connections on multiple pages

- **TestPageMapperEntry**: PageMapperEntry dataclass
  - Creation, hashability, equality

- **TestGodEdgeCasesAdditional**: Additional edge cases
  - Connections with links and multiple attributes
  - Standalone links
  - Multiple XTarget types
  - Deep pin chains
  - Virtual cable connections

## Coverage

Current coverage for `src/indu_doc/god.py`: **99%** (151 statements, 2 missed)

### Uncovered Lines
- Lines 179-180: Defensive check for impossible case where `current_pin` is None after loop
  - This is a defensive check that should never be reached with valid input
  - Would require the pin chain to be processed but result in no pin object

## Running Tests

### Run all God tests
```bash
uv run pytest tests/god_tests/ -v
```

### Run specific test file
```bash
uv run pytest tests/god_tests/test_god_coverage.py -v
```

### Run with coverage
```bash
uv run pytest tests/god_tests/ --cov=src/indu_doc/god --cov-report=term-missing
```

### Run specific test class
```bash
uv run pytest tests/god_tests/test_god_coverage.py::TestPagesObjectsMapper -v
```

## Test Fixtures

Located in `tests/conftest.py`:
- `test_config`: Standard AspectsConfig for testing
- `god_instance`: God factory instance with test config
- `mock_page_info`: PageInfo with sample footer
- `mock_page_info_no_footer`: PageInfo without footer tags
- `sample_footer`: PageFooter with tags
- `empty_footer`: PageFooter without tags

## Key Testing Patterns

1. **Object Creation**: Test that objects are created with correct attributes
2. **Caching**: Verify that identical objects return the same instance
3. **Merging**: Test that similar objects merge attributes correctly
4. **Error Handling**: Test None returns for invalid inputs
5. **Page Mapping**: Verify bidirectional page-object relationships
6. **Edge Cases**: Test boundary conditions and unusual inputs

## Notes

- All tests pass without modifying source code
- Tests use mock objects for PDF pages to avoid file dependencies
- Coverage tests specifically target previously untested code paths
- Focus on factory pattern, caching, and page mapping functionality
