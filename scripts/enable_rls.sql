-- [WF5] Row-Level Security para aislamiento por tenant (Postgres).
-- OPT-IN: ejecutar SOLO al migrar a multi-tenant (4+ clientes) y después de
-- poblar tenant_id en todas las filas. Defensa en profundidad: aunque una query
-- olvide el filtro de aplicación, la BD no devuelve filas de otro tenant.
--
-- Requiere que la app ejecute, al abrir cada sesión:
--    SET app.tenant_id = '<codigo_tenant>';   (ver tenant_filter.set_rls_tenant)

DO $$
DECLARE t text;
BEGIN
  FOREACH t IN ARRAY ARRAY['students','grades','interventions','enrollments','avac_accesses','task_submissions']
  LOOP
    EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY;', t);
    EXECUTE format('DROP POLICY IF EXISTS tenant_isolation ON %I;', t);
    EXECUTE format($f$
      CREATE POLICY tenant_isolation ON %I
      USING (tenant_id IS NOT DISTINCT FROM current_setting('app.tenant_id', true));
    $f$, t);
  END LOOP;
END $$;
