## Known Limitations

### Language-Specific Limitations

**Python:**
- ✅ All hit condition modes supported (`>`, `>=`, `=`, `<`, `<=`, `%`, exact)
- ✅ All debugging features fully functional

**JavaScript/TypeScript:**
- ℹ️ Attach mode connects to an already-running process (requires `--inspect` or `--inspect-brk` flag)
- ✅ All hit condition modes supported (`>`, `>=`, `=`, `<`, `<=`, `%`, exact)
- ✅ All debugging features fully functional

**Java:**
- ⚠️ Hit conditions: EXACT mode only (plain integers like `"5"`)
- ❌ Hit condition operators (`>`, `>=`, `<`, `<=`, `%`, `==`) not supported by Java debug adapter
- ✅ Conditional breakpoints fully supported
- ✅ Logpoints fully supported
