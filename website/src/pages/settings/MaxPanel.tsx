import { useEffect } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import { api } from '../../api/client'
import ErrorNotice from '../../components/ErrorNotice'
import { Btn } from '../../components/ui'
import { i18nT } from '../../i18n/t'

/** The host owner pairs from Settings; the backend remains the authority. */
export function MaxPanel() {
  const status = useQuery({
    queryKey: ['max-config'], queryFn: api.getMaxConfig,
    refetchInterval: 3000, retry: false,
  })
  const pairing = useMutation({ mutationFn: api.issueMaxPairing, gcTime: 0 })
  const subscription = useMutation({ mutationFn: api.registerMaxSubscription, retry: false })
  const paired = Boolean(status.data?.owner_id)
  const reset = pairing.reset
  useEffect(() => {
    if (paired) reset()
  }, [paired, reset])
  useEffect(() => {
    if (!pairing.data) return
    const timer = setTimeout(reset, pairing.data.expires_in * 1000)
    return () => clearTimeout(timer)
  }, [pairing.data, reset])
  const error = status.error || pairing.error || subscription.error
  return (
    <section className="space-y-4">
      {error && <ErrorNotice message={error.message} askAgent />}
      <p>{i18nT('pages.settings.maxPanel.guide')}</p>
      {status.data?.delivery_mode === 'webhook' && <div className="space-y-2">
        <p>{i18nT('pages.settings.maxPanel.subscription_hint')}</p>
        <Btn type="button" disabled={!status.data.ready || subscription.isPending}
          onClick={() => subscription.mutate()}>
          {i18nT('pages.settings.maxPanel.subscribe')}
        </Btn>
        {subscription.isSuccess && <p role="status">{i18nT('pages.settings.maxPanel.subscribed')}</p>}
      </div>}
      {paired ? <p role="status">{i18nT('pages.settings.maxPanel.paired', { id: status.data!.owner_id })}</p> : (
        <>
          {!status.isPending && !status.data?.ready && <p>{i18nT('pages.settings.maxPanel.inactive')}</p>}
          <Btn type="button"
            disabled={!status.data?.ready || pairing.isPending}
            onClick={() => pairing.mutate()}>
            {i18nT('pages.settings.maxPanel.pair')}
          </Btn>
          {pairing.data && <div role="status">
            <p>{i18nT('pages.settings.maxPanel.code_hint')}</p>
            <code className="select-all break-all">{`/start ${pairing.data.code}`}</code>
          </div>}
        </>
      )}
    </section>
  )
}
