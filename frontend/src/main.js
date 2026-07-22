import { createApp } from 'vue'
import {
  ElBadge, ElButton, ElCard, ElCol, ElContainer, ElDatePicker, ElDescriptions,
  ElDescriptionsItem, ElDialog, ElEmpty, ElForm, ElFormItem, ElHeader, ElIcon,
  ElInput, ElInputNumber, ElMain, ElMenu, ElMenuItem, ElOption, ElPageHeader,
  ElPagination, ElRadio, ElRadioGroup, ElRow, ElSelect, ElTable, ElTableColumn, ElTag,
} from 'element-plus'
import 'element-plus/dist/index.css'
import { createPinia } from 'pinia'
import App from './App.vue'
import router from './router'
import './styles.css'

const app = createApp(App)
for (const component of [
  ElBadge, ElButton, ElCard, ElCol, ElContainer, ElDatePicker, ElDescriptions,
  ElDescriptionsItem, ElDialog, ElEmpty, ElForm, ElFormItem, ElHeader, ElIcon,
  ElInput, ElInputNumber, ElMain, ElMenu, ElMenuItem, ElOption, ElPageHeader,
  ElPagination, ElRadio, ElRadioGroup, ElRow, ElSelect, ElTable, ElTableColumn, ElTag,
]) app.component(component.name, component)
app.use(createPinia())
app.use(router)
app.mount('#app')
