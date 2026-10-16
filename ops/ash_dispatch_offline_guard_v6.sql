-- CANDIDATE ONLY — NOT DEPLOYED. Requires staging SQL integration and rollback verification.
-- Safety goal: defer due remote automations while no eligible desktop device
-- has heartbeated in the last five minutes. Do not delete jobs, disable
-- automations, or advance last_run_at for deferred runs.
-- Stage with representative data and validate cron/desktop reconnect before production.
-- Exclude CI/test device platforms even if they report fresh heartbeats.
-- Reject implausibly future-dated heartbeats to avoid indefinite fake liveness.
-- Never allow malformed schedule/approval values to abort a whole dispatcher batch.
-- Do not replay days or weeks of missed daily/weekly jobs on reconnect.
-- Force approval for command and builder jobs; workers must enforce approval too.
-- If multiple trusted devices are online for untargeted work, defer instead of
-- selecting a potentially wrong computer. Explicitly target such automations.
CREATE OR REPLACE FUNCTION public.ash_dispatch_due_automations()
RETURNS integer
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO 'public'
AS $function$
DECLARE
  rec record;
  dispatched integer := 0;
  repeat_minutes integer;
  next_time timestamptz;
  safe_target_device_id uuid;
  target_text text;
  eligible_device_count integer;
BEGIN
  FOR rec IN
    SELECT * FROM public.jarvis_automations
    WHERE enabled = true AND next_run_at IS NOT NULL AND next_run_at <= now()
    ORDER BY next_run_at ASC LIMIT 100 FOR UPDATE SKIP LOCKED
  LOOP
    safe_target_device_id := NULL;
    eligible_device_count := 0;
    target_text := nullif(rec.action_config->>'target_device_id','');

    -- Never cast a malformed target or silently route it to a different device.
    IF target_text IS NOT NULL AND
       target_text !~* '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$' THEN
      UPDATE public.jarvis_automations
      SET next_run_at = now() + interval '5 minutes', updated_at = now()
      WHERE id = rec.id;
      CONTINUE;
    END IF;

    -- Resolve an online, trusted device belonging to the automation owner.
    -- Untargeted work is safe to route only when there is exactly ONE
    -- eligible device; ambiguous routing must not select an arbitrary PC.
    SELECT count(*)::integer, min(d.id::text)::uuid
      INTO eligible_device_count, safe_target_device_id
    FROM public.jarvis_devices d
    WHERE d.user_id = rec.user_id
      AND d.is_trusted = true
      AND d.last_seen_at > now() - interval '5 minutes'
      AND d.last_seen_at <= now() + interval '1 minute'
      AND coalesce(lower(d.platform), '') NOT IN ('linux-ci', 'test')
      AND (target_text IS NULL OR d.id = target_text::uuid);

    IF eligible_device_count <> 1 OR safe_target_device_id IS NULL THEN
      -- Keep the automation enabled; no remote job is created and
      -- last_run_at is NOT advanced while its desktop is unavailable.
      UPDATE public.jarvis_automations
      SET next_run_at = now() + interval '5 minutes', updated_at = now()
      WHERE id = rec.id;
      CONTINUE;
    END IF;

    INSERT INTO public.jarvis_remote_jobs
      (user_id,target_device_id,kind,mode,payload,requires_confirmation,expires_at)
    VALUES (
      rec.user_id,safe_target_device_id,
      CASE WHEN rec.action_config->>'kind' IN ('command','builder','chat_fallback')
           THEN rec.action_config->>'kind' ELSE 'mission' END,
      CASE WHEN rec.action_config->>'mode' IN ('instant','medium','high')
           THEN rec.action_config->>'mode' ELSE 'medium' END,
      jsonb_build_object(
        'prompt',coalesce(rec.action_config->>'prompt',rec.description,rec.name),
        'automation_id',rec.id,'automation_name',rec.name,'source','automation'
      ),
      CASE
        WHEN rec.action_config->>'kind' IN ('command','builder') THEN true
        WHEN lower(rec.action_config->>'requires_confirmation') IN ('true','false')
          THEN (rec.action_config->>'requires_confirmation')::boolean
        ELSE true
      END,
      now() + interval '24 hours'
    );
    repeat_minutes := CASE
      WHEN rec.trigger_config->>'repeat_minutes' ~ '^[0-9]{1,5}$'
        THEN greatest(1, least((rec.trigger_config->>'repeat_minutes')::integer, 10080))
      ELSE 1
    END;
    IF rec.trigger_type = 'once' THEN
      UPDATE public.jarvis_automations
      SET last_run_at=now(),next_run_at=NULL,enabled=false,updated_at=now()
      WHERE id=rec.id;
    ELSIF rec.trigger_type = 'interval' THEN
      next_time := greatest(rec.next_run_at + make_interval(mins=>repeat_minutes),now()+interval '1 minute');
      UPDATE public.jarvis_automations
      SET last_run_at=now(),next_run_at=next_time,updated_at=now()
      WHERE id=rec.id;
    ELSIF rec.trigger_type = 'daily' THEN
      UPDATE public.jarvis_automations
      SET last_run_at=now(),next_run_at=greatest(rec.next_run_at+interval '1 day',now()+interval '1 minute'),updated_at=now()
      WHERE id=rec.id;
    ELSIF rec.trigger_type = 'weekly' THEN
      UPDATE public.jarvis_automations
      SET last_run_at=now(),next_run_at=greatest(rec.next_run_at+interval '7 days',now()+interval '1 minute'),updated_at=now()
      WHERE id=rec.id;
    ELSE
      UPDATE public.jarvis_automations
      SET last_run_at=now(),next_run_at=NULL,enabled=false,updated_at=now()
      WHERE id=rec.id;
    END IF;
    dispatched := dispatched + 1;
  END LOOP;
  RETURN dispatched;
END;
$function$;
