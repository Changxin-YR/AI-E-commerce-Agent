import Taro from '@tarojs/taro'
import { account, selectShop } from './session'
import { queryString } from './task-policy'

export const routes: Record<string, string> = {
  '/': '/pages/operations/index',
  '/imports': '/pages/imports/index',
  '/agent': '/pages/agent/index',
  '/settings': '/pages/settings/index',
}
export async function openLink(
  path: string,
  query: Record<string, string> = {},
): Promise<void> {
  const target = routes[path]
  if (!target) throw new Error('该业务页面正在接入，请保留记录编号稍后回读。')
  const shop = Number(query.shop || account.shopId)
  if (shop && shop !== account.shopId) {
    if (!account.shops.some((item) => item.id === shop))
      throw new Error('关联店铺不在当前账号范围。')
    const answer = await Taro.showModal({
      title: '切换关联店铺',
      content: `该记录属于 ${account.shops.find((item) => item.id === shop)?.name}，是否切换？`,
    })
    if (!answer.confirm) return
    selectShop(shop)
  }
  await Taro.navigateTo({ url: `${target}?${queryString(query)}` })
}
