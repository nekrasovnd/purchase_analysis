import{ht as e,mt as t}from"../chunks/config-Bxu74h9U.js";$(function(){let n=[],r=[],i=[];var a={slidesToShow:5,slidesToScroll:1,infinite:!1,responsive:[{breakpoint:1180,settings:{slidesToShow:4}},{breakpoint:1024,settings:{slidesToShow:3}},{breakpoint:700,settings:{slidesToShow:2}},{breakpoint:480,settings:{slidesToShow:1}}]};function o(){r.length&&r.forEach(function(e){n=n.concat(e.skuIds)})}function s(e){e.forEach(function(e){var t,n=`/img/placeholder/sample_200x200.jpg`;Object.hasOwn(e,`picture`)?(t=e.picture,n=t?t.replace(`.`,`_200x200.`):n):Object.hasOwn(e.product,`file`)&&(t=e.product.file,n=t?`/uploads`+t.path+t.replace(`.`,`_200x200.`):n),e.image=n})}function c(e){var t=[],n=e.product,r=e.product.attributes;return n&&Object.keys(n).length&&(t.push({group:`root`,name:`Бренд`,value:n.brand_name||`---`}),t.push({group:`root`,name:`Производитель`,value:n.manufacturer||`---`}),t.push({group:`root`,name:`Страна происхождения`,value:n.manufacturer_country||`---`})),r?.length>0&&r.forEach(function(e){var n={group:``,name:``,value:``};if(n.name=e.attribute.name||`нечто`,e.value!==void 0)switch(e.value){case!1:n.value=`Нет`;break;case!0:n.value=`Да`;break;case`no information`:n.value=`Не предоставлена`;break;case`NoInformation`:n.value=`Не предоставлена`;break;default:e.value.name?n.value=e.value.name:n.value=`---`}else e.attribute.options?.length>0&&e.attribute.options.forEach(function(e){n.value+=e.name+`, `});n.group=e.attribute.group.name?e.attribute.group.name:`root`,t.push(n)}),t}u(),p(r),m(r),$(`#sec-compare`).length&&l();function l(){var i=$(`#compare-tabs-head`),a=$(`#compare-tabs-body`),s=$(`#sec-compare`);a.html(``),i.html(``),r.length?i.length&&a.length&&(o(),r.length&&n.length&&(y(n),s.removeClass(`is-empty`))):(a.append(`
                <div class="container" id="compare-body-empty">
                    <div class="sec_compare__empty">
                        <h4 class="mb-4">
                            В сравнении пока ничего нет
                        </h4>
                        <div class="sec_compare__empty-note">
                            Вы можете добавлять в сравнение товары и услуги из каталога.
                        </div>
                        <nav class="sec_compare__empty-nav">
                            <a class="sec_compare__empty-link" href="${Route.generate(`category_show`,{id:t})}">
                                Каталог товаров
                            </a>
                            <a class="sec_compare__empty-link" href="${Route.generate(`category_show`,{id:e})}">
                                Каталог услуг
                            </a>
                        </nav>
                    </div>
                </div>
            `),s.addClass(`is-empty`))}function u(){var e;try{r=JSON.parse(localStorage.getItem(`compareProdData`))||[]}catch{console.warn(`Compare: fail to parse compareProdData`),r=[]}e=JSON.parse(App.compareProdData||`[]`),Array.isArray(e)&&e.length!==0&&(r.length===0?r=e:d(e))}function d(e){e.forEach(function(e){e.skuIds.forEach(function(t){h(t,e.categoryId,e.categoryName,!1)})}),f()}async function f(){await $.ajax({method:`POST`,data:{comparison_list:JSON.stringify(r)},url:Route.generate(`compare_save_products_comparison`),dataType:`json`,cache:!1,error(){},success(e){}})}function p(e){var t=[],n=$(`.js-compare-switch`);e.length&&(e.forEach(function(e){t=t.concat(e.skuIds)}),n.each(function(e,n){var r=n.getAttribute(`data-skuid`);r&&$.inArray(r,t)!==-1&&(n.className+=` is-active`)}))}function m(e){var t=[],n=$(`.js-compare-count`);e.length&&e.forEach(function(e){t=t.concat(e.skuIds)}),n.text(t.length)}function h(e,t,n,i){var a=!1;r.forEach(function(n){n.categoryId===t&&(a=!0,$.inArray(e,n.skuIds)===-1&&n.skuIds.push(e))}),a||r.push({categoryName:n,categoryId:t,skuIds:[e]}),i&&(localStorage.setItem(`compareProdData`,JSON.stringify(r)),rippleHeaderLink(`#header-compare-link`),m(r))}async function g(e){r.forEach(function(t,n){var i=$.inArray(e,t.skuIds);i!==-1&&t.skuIds.splice(i,1),t.skuIds.length===0&&r.splice(n,1)}),localStorage.setItem(`compareProdData`,JSON.stringify(r)),m(r),rippleHeaderLink(`#header-compare-link`),await f()}async function _(e){r.forEach(function(t,n){t.categoryId===e&&r.splice(n,1)}),localStorage.setItem(`compareProdData`,JSON.stringify(r)),m(r),await f()}$(document).on(`click`,`.js-compare-switch`,function(){var e=$(this),t=e.hasClass(`is-active`),n=e.data(`category-name`),r=e.data(`category-id`),i=e.data(`skuid`);t?i&&(g(i),e.removeClass(`is-active`)):n&&r&&i?(h(i,r,n,!0),f(),e.addClass(`is-active`)):console.error(`Не хватает обязательных данных для добавления к сравнению`)});function v(e){var t=``;r.length&&(r.forEach(function(e,n){t+=`
                    <a
                        class="compare_nav__btn js-compare-tab-btn ${n===0?`is-active`:``}"
                        data-tab="${e.categoryId}"
                        data-category-id="${e.categoryId}"
                        role="button"
                    >
                        ${e.categoryName}
                        <strong class="js-compare-card-count">
                            ${e.skuIds.length}
                        </strong>
                    </a>
                `}),e.append(t),$(`#compare-cat-clear`).attr(`data-category-id`,$(`.js-compare-tab-btn.is-active`).data(`category-id`)))}async function y(e){var t=$(`#compare-tabs-head`),n=$(`#compare-tabs-body`);if(!Array.isArray(e)&&!e.length)return!1;$(`#site-wrapper`).addClass(`has-main-modal-loading`),await $.ajax({method:`POST`,data:{ids:e},url:Route.generate(`compare_get_products_by_ids`),dataType:`json`,cache:!1,error(){return console.error(`Error loading products`),n.append(`
                    <div class="container" id="compare-body-empty">
                        <div class="sec_compare__empty">
                            <h4 class="sec_compare__empty-title">Не удалось загрузить товары</h4>
                            <div class="sec_compare__empty-note">
                                Добавленные ранее для сравнения товары не удалось загрузить. <br>
                                Обновите страницу и проверьте состояние подключения к интернету.
                            </div>
                        </div>
                    </div>
                `),$(`#site-wrapper`).removeClass(`has-main-modal-loading`),!1},success(a){var o=a.data.products;e.length!==o.length&&e.forEach(function(e){var t=!1;o.forEach(function(n){n.sku_id===e&&(t=!0)}),t||g(e)}),r.forEach(function(e){e.skuIds.forEach(function(t,n){o.forEach(function(n){n.sku_id===t&&(n.catId=e.categoryId)})})}),r.length?(s(o),o.forEach(function(e){e.attrSet=c(e)}),b(o),x(o),v(t),S(o),i=o,$(`#site-wrapper`).removeClass(`has-main-modal-loading`)):(n.append(`
                        <div class="container" id="compare-body-empty">
                            <div class="sec_compare__empty">
                                <h4 class="sec_compare__empty-title">Нет товаров, добавленных для сравнения</h4>
                                <div class="sec_compare__empty-note">
                                    Добавленные ранее для сравнения товары в настоящее время сняты с продажи
                                    и были удалены из вашего списка сравнения. Вы можете выбрать подобные, из актуальных
                                    в настоящее время предложений.
                                </div>
                            </div>
                        </div>
                    `),$(`#site-wrapper`).removeClass(`has-main-modal-loading`))}})}function b(e){r.forEach(function(t){var n=[];t.skuIds.forEach(function(t){e.forEach(function(e){e.sku_id===t&&e.attrSet.forEach(function(e){var t=!0;n.length&&n.forEach(function(n){n[0]===e.group&&n[1]===e.name&&(t=!1)}),t&&n.push([e.group,e.name])})})}),n.sort(function(e,t){return e[0]>t[0]?1:e[0]<t[0]?-1:0}),t.skuIds.forEach(function(t){e.forEach(function(e){var r=[];e.sku_id===t&&(n.forEach(function(t){var n=!0;e.attrSet.forEach(function(e){t[0]===e.group&&t[1]===e.name&&n&&(n=!1,r.push(e))}),n&&r.push({group:t[0],name:t[1],value:`---`})}),e.attrSetDecorated=r)})})})}function x(e){r.forEach(function(t,n){var r,i=t.skuIds.length;e.forEach(function(n,a){n.catId===t.categoryId&&r===void 0&&(r=a,i===1?n.attrSetDecorated.forEach(function(e){e.isDifferent=!0}):n.attrSetDecorated.forEach(function(n,r){var i=!1;e.forEach(function(e){if(e.catId===t.categoryId){var a=e.attrSetDecorated[r];n.value!==a.value&&(i=!0)}}),e.forEach(function(e){e.catId===t.categoryId&&(e.attrSetDecorated[r].isDifferent=i)})}))})})}function S(e){var t,n;e.length&&(t=$(`#compare-tabs-body`),n=``,r.forEach(function(t,r){var i=``;t.skuIds.forEach(function(t){e.forEach(function(e){e.sku_id===t&&(i+=C(e))})}),n+=`
                    <div
                        class="sec_compare__tab js-tabs-item ${r===0?`is-active`:``}"
                        id="${t.categoryId}"
                    >
                        <div class="container">
                            <div class="sec_compare__slider js-compare-slider">
                                ${i}
                            </div><!-- END sec_compare__slider -->
                        </div><!-- END container -->
                    </div><!-- END sec_compare__tab -->
                `}),t.append(n),$(`.js-compare-slider`).slick(a)),$(`#site-wrapper`).removeClass(`has-main-modal-loading`)}function C(e){var t=``,n=`add_featured`,r=``,i=``,a=``;if(e.attrSetDecorated.forEach(function(e){var n=e.isDifferent?`is-various`:`is-equal`,r=(``+e.value).length>24;t+=`
                <li class="compare_card__prop ${n}">
                    <span class="compare_card__prop_name">
                        ${e.name+(e.group===`root`?``:` / `+e.group)}
                    </span>
                    <span class="compare_card__prop_data"
                        ${r?`title="`+e.value+`"`:``}>
                        ${e.value}
                    </span>
                </li>
            `}),$.inArray(e.sku_id,Featured.productsSkuIds)!==-1&&(n=`delete_featured`),e.product.manufacturer&&e.product.manufacturer_code&&e.product.manufacturer_code!==`1000000`&&e.product.manufacturer_code!==`NoName`&&(r=`, `),e.product.manufacturer_code&&e.product.manufacturer_code!==`1000000`&&e.product.manufacturer_code!==`NoName`&&(i=e.product.manufacturer_code),a=e.price.value?insertSpaces(e.price.value)+` `+(e.price.currency===`RUR`?`руб`:e.price.currency):`Цена договорная`,e.visible){let o=`
                <div
                    class="sec_compare__slide"
                    id ="${e.sku_id}"
                    data-skuid="${e.sku_id}"
                    data-catid="${e.catId}"
                >
                    <div class="compare_card">
                        <a
                            class="compare_card__pict"
                            href="${Route.generate(`product_show`,{catalogCategoryTree:e.category_id||``,skuId:e.sku_id||``})}"
                            title="Открыть в отдельном окне"
                        >
                            <img
                                class="compare_card__img"
                                src="${e.image}"
                                alt="${e.full_name}"
                            >
                        </a>
                        <div class="compare_card__text">
                            <h4 class="compare_card__title">${e.full_name}</h4>
                            <div class="compare_card__type">${e.product.manufacturer+r+i}</div>
                            <div class="compare_card__cost">${a}</div>
                            <div class="compare_card__actions">
                `;return e.company.verified?o+=`
                    <a
                        class="compare_card__get btn btn--green btn_add_to_basket"
                        data-sku-id="${e.sku_id}"
                        data-sku-count="1"
                        role="button"
                        onclick="toBasket(this)"
                    >В корзину</a>
                `:o+=`
                    <a
                        class="compare_card__get btn btn--green btn_add_to_basket"
                        data-sku-id="${e.sku_id}"
                        data-sku-count="1"
                        role="button"
                        onclick="window.location = '${window.location.protocol}//${e.company.web_info.domain}.${window.location.host}"
                    >Связаться</a>
                `,o+=`
                                <a class="compare_card__btn compare_card__btn--del js-compare-card-del" role="button"></a>
                                <a
                                    class="compare_card__btn compare_card__btn--fav js-favorites-switch ${n}"
                                    data-skuid="${e.sku_id}"
                                    role="button"
                                ><i class="icon-star-fill"></i></a>
                            </div>
                            <ul class="compare_card__props">
                                ${t}
                            </ul>
                        </div>
                    </div>
                </div>
            `,o}return`
            <div
                class="sec_compare__slide"
                id ="${e.sku_id}"
                data-skuid="${e.sku_id}"
                data-catid="${e.catId}"
            >
                <div class="compare_card is-not-present" title="Товар снят с продажи">
                    <div class="compare_card__pict">
                        <img
                            class="compare_card__img"
                            src="${e.image}"
                            alt="${e.full_name}"
                        >
                    </div>
                    <div class="compare_card__text">
                        <h4 class="compare_card__title">${e.full_name}</h4>
                        <div class="compare_card__type">${e.product.manufacturer+r+i}</div>
                        <div class="compare_card__cost">${a}</div>
                        <div class="compare_card__actions">
                            <a class="compare_card__get btn btn--outline js-compare-card-del" role="button">Удалить</a>
                            <a class="compare_card__btn compare_card__btn--del js-compare-card-del" role="button"></a>
                        </div>
                        <ul class="compare_card__props">
                            ${t}
                        </ul>
                    </div>
                </div>
            </div>
        `}$(document).on(`click`,`.js-compare-tab-btn`,function(){var e=$(this),t=e.siblings(`.js-compare-tab-btn`),n=$(`#compare-tabs-body`).children(`.js-tabs-item`),r=`#`+e.data(`tab`);t.removeClass(`is-active`),e.addClass(`is-active`),n.removeClass(`is-active`),$(r).addClass(`is-active`),$(`#compare-cat-clear`).attr(`data-category-id`,e.data(`category-id`))});var w=$(`.js-compare-set`);if(w.length){function e(e){var t=$(e),n=t.closest(`.sec_compare`).children(`.sec_compare__body`),r=t.val();switch(r){case`is-all-props`:n.addClass(r).removeClass(`is-only-various`);break;case`is-only-various`:n.addClass(r).removeClass(`is-all-props`);break;default:console.error(`compareRadioSet: unknown value`)}}w.click(function(){e(this)})}$(document).on(`click`,`.js-compare-card-del`,async function(){var e=$(this),t=e.closest(`.js-compare-slider`),n=e.closest(`.sec_compare__slide`),r=+n.data(`slick-index`),o=n.data(`skuid`),s=n.data(`catid`),c,u=0,d=$(`.js-compare-tab-btn.is-active`);t.slick(`slickRemove`,r).slick(`unslick`).slick(a),c=t.find(`.sec_compare__slide`),c.each(function(){$(this).attr(`data-slick-index`,u),u++}),await g(o),d.children(`.js-compare-card-count`).text(u),i.forEach(function(e,t){e.sku_id===o&&i.splice(t,1)}),u===0?l():(b(i),x(i),i.forEach(function(e,t){var n=``;if(e.catId===s){var r=$(`#`+e.sku_id).find(`.compare_card__props`);r.empty(),e.attrSetDecorated.forEach(function(e){var t=e.isDifferent?`is-various`:`is-equal`,r=(``+e.value).length>24;n+=`
                            <li class="compare_card__prop ${t}">
                                <span class="compare_card__prop_name">
                                    ${e.name+(e.group===`root`?``:` / `+e.group)}
                                </span>
                                <span
                                    class="compare_card__prop_data"
                                    ${r?`title="`+e.value+`"`:``}
                                >
                                    ${e.value}
                                </span>
                            </li>
                        `}),r.append(n)}}))}),$(document).on(`click`,`#compare-cat-clear`,function(){var e=$(this),t=e.attr(`data-category-id`);e.promptCreate({promptTitle:`Удаление товаров из сравнения`,promptText:`Вы уверены, что хотите удалить все товары этого типа из сравнения?`,promptBtnText:`Да, удалить`,async promptCallback(){await _(t),l()}})})});